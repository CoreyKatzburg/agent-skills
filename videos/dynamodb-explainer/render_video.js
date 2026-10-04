// Renders video.html into an MP4, one frame at a time, using headless Chromium and ffmpeg.
//
//   node render_video.js                     full video  -> build/dynamodb-explainer.mp4
//   node render_video.js --stills 12,40.5    still images -> build/stills/frame-<seconds>.png
//   node render_video.js --workers 4 --fps 30
//
// Each frame is drawn by calling window.renderFrame(seconds) in the page, so the
// result does not depend on how fast this machine is. Several browser pages render
// different stretches of the video at the same time; the pieces are joined at the end.

const { chromium } = require("playwright");
const { spawn, execFileSync } = require("child_process");
const fs = require("fs");
const http = require("http");
const path = require("path");

const projectFolder = __dirname;
const buildFolder = path.join(projectFolder, "build");

function readOption(name, fallback) {
  const index = process.argv.indexOf(`--${name}`);
  return index === -1 ? fallback : process.argv[index + 1];
}
const framesPerSecond = Number(readOption("fps", 30));
const workerCount = Number(readOption("workers", 4));
const stillTimes = readOption("stills", null);
const outputPath = path.join(buildFolder, readOption("output", "dynamodb-explainer.mp4"));

/** A tiny static file server, because browsers refuse to load fonts straight from disk. */
function startFileServer() {
  const contentTypes = { ".html": "text/html", ".js": "text/javascript", ".woff2": "font/woff2", ".wav": "audio/wav", ".css": "text/css" };
  const server = http.createServer((request, response) => {
    const filePath = path.join(projectFolder, decodeURIComponent(new URL(request.url, "http://localhost").pathname));
    if (!filePath.startsWith(projectFolder) || !fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
      response.writeHead(404).end();
      return;
    }
    response.writeHead(200, { "Content-Type": contentTypes[path.extname(filePath)] || "application/octet-stream" });
    fs.createReadStream(filePath).pipe(response);
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(server)));
}

async function openVideoPage(browser, pageUrl) {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on("pageerror", (error) => console.error("page error:", error.message));
  await page.goto(pageUrl);
  await page.evaluate(() => document.fonts.ready);
  const cueErrors = await page.evaluate(() => window.CUE_ERRORS);
  if (cueErrors.length) throw new Error(`Animation cues failed:\n${cueErrors.join("\n")}`);
  return page;
}

async function drawFrame(page, seconds, screenshotOptions) {
  await page.evaluate((time) => window.renderFrame(time), seconds);
  return page.screenshot(screenshotOptions);
}

async function renderStills(browser, pageUrl) {
  const page = await openVideoPage(browser, pageUrl);
  const stillsFolder = path.join(buildFolder, "stills");
  fs.mkdirSync(stillsFolder, { recursive: true });
  for (const seconds of stillTimes.split(",").map(Number)) {
    const filePath = path.join(stillsFolder, `frame-${seconds.toFixed(1).padStart(6, "0")}.png`);
    await drawFrame(page, seconds, { path: filePath, type: "png" });
    console.log(filePath);
  }
}

async function renderSegment(browser, pageUrl, firstFrame, frameCount, segmentPath, onFrameDone) {
  const page = await openVideoPage(browser, pageUrl);
  const encoder = spawn("ffmpeg", [
    "-v", "error", "-y",
    "-f", "image2pipe", "-c:v", "mjpeg", "-framerate", String(framesPerSecond), "-i", "-",
    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", String(framesPerSecond),
    segmentPath,
  ], { stdio: ["pipe", "inherit", "inherit"] });
  const encoderFinished = new Promise((resolve, reject) => encoder.on("close", (code) => (code === 0 ? resolve() : reject(new Error(`ffmpeg exited with ${code}`)))));

  for (let frame = firstFrame; frame < firstFrame + frameCount; frame++) {
    const image = await drawFrame(page, frame / framesPerSecond, { type: "jpeg", quality: 92 });
    if (!encoder.stdin.write(image)) await new Promise((resolve) => encoder.stdin.once("drain", resolve));
    onFrameDone();
  }
  const renderErrors = await page.evaluate(() => window.RENDER_ERRORS);
  if (renderErrors.length) console.error("render warnings:", [...new Set(renderErrors)].slice(0, 10));
  encoder.stdin.end();
  await encoderFinished;
  await page.close();
}

async function renderFullVideo(browser, pageUrl) {
  const probePage = await openVideoPage(browser, pageUrl);
  const duration = await probePage.evaluate(() => window.VIDEO_DURATION);
  await probePage.close();
  const totalFrames = Math.ceil(duration * framesPerSecond);
  const framesPerWorker = Math.ceil(totalFrames / workerCount);
  const segmentsFolder = path.join(buildFolder, "segments");
  fs.mkdirSync(segmentsFolder, { recursive: true });

  let framesDone = 0;
  const startedAt = Date.now();
  const reportProgress = () => {
    framesDone += 1;
    if (framesDone % 300 === 0 || framesDone === totalFrames) {
      const elapsedSeconds = (Date.now() - startedAt) / 1000;
      console.log(`${framesDone}/${totalFrames} frames  (${elapsedSeconds.toFixed(0)}s elapsed)`);
    }
  };

  const segmentPaths = [];
  const jobs = [];
  for (let worker = 0; worker < workerCount; worker++) {
    const firstFrame = worker * framesPerWorker;
    const frameCount = Math.min(framesPerWorker, totalFrames - firstFrame);
    if (frameCount <= 0) break;
    const segmentPath = path.join(segmentsFolder, `segment-${worker}.mp4`);
    segmentPaths.push(segmentPath);
    jobs.push(renderSegment(browser, pageUrl, firstFrame, frameCount, segmentPath, reportProgress));
  }
  await Promise.all(jobs);

  const segmentList = path.join(segmentsFolder, "list.txt");
  fs.writeFileSync(segmentList, segmentPaths.map((segmentPath) => `file '${segmentPath}'`).join("\n"));
  execFileSync("ffmpeg", [
    "-v", "error", "-y",
    "-f", "concat", "-safe", "0", "-i", segmentList,
    "-i", path.join(buildFolder, "voiceover.wav"),
    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart",
    outputPath,
  ], { stdio: "inherit" });
  console.log(`done: ${outputPath}`);
}

(async () => {
  const server = await startFileServer();
  const pageUrl = `http://127.0.0.1:${server.address().port}/video.html`;
  const browser = await chromium.launch();
  try {
    if (stillTimes) await renderStills(browser, pageUrl);
    else await renderFullVideo(browser, pageUrl);
  } finally {
    await browser.close();
    server.close();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
