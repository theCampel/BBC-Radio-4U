// frontend/visualiser.js
//
// Simple single-canvas visualisation for host audio (Matt & Mollie only).

let hostCanvas, hostCtx;

/**
 * Initialize the canvas/context for drawing the host waveform.
 */
export function initVisualiser() {
  hostCanvas = document.getElementById("hostCanvas");
  if (!hostCanvas) {
    console.warn("No #hostCanvas found; visualiser won't render");
    return;
  }
  hostCtx = hostCanvas.getContext("2d");

  // Clear once at startup
  hostCtx.fillStyle = "#FFF";
  hostCtx.fillRect(0, 0, hostCanvas.width, hostCanvas.height);
}

/**
 * Clear the canvas (used when stopping streams, etc.).
 */
export function resetVisualiser() {
  if (!hostCtx) return;
  hostCtx.clearRect(0, 0, hostCanvas.width, hostCanvas.height);
  hostCtx.fillStyle = "#FFF";
  hostCtx.fillRect(0, 0, hostCanvas.width, hostCanvas.height);
}

/**
 * Render a very simple amplitude bar for each raw PCM chunk.
 * This is intentionally simplified. 
 * If you prefer a more advanced wave shape, you can expand this logic.
 */
export function updateVisualiser(audioData, speaker) {
  if (!hostCtx) return;

  // 1) Compute an average amplitude
  //    Each pair of bytes = 16-bit sample
  let total = 0;
  for (let i = 0; i < audioData.length; i += 2) {
    // little-endian 16-bit
    const sample = (audioData[i] | (audioData[i + 1] << 8));
    total += Math.abs(sample);
  }
  const avg = total / (audioData.length / 2);
  // Normalised amplitude [0..1]
  const amplitude = avg / 32768;

  // 2) Clear old display
  hostCtx.clearRect(0, 0, hostCanvas.width, hostCanvas.height);

  // 3) Choose color per speaker
  const color = (speaker === "matt") ? "blue" : "red";

  // 4) Draw a filled bar. 
  //    E.g. bar height goes up to 80% of canvas.
  const barHeight = amplitude * (hostCanvas.height * 0.8);
  const x = 0;
  const y = hostCanvas.height - barHeight;
  const width = hostCanvas.width;
  
  hostCtx.fillStyle = color;
  hostCtx.fillRect(x, y, width, barHeight);
}
