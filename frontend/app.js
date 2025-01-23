// frontend/app.js

import {
    initVisualiser,
    resetVisualiser,
    updateVisualiser
  } from "./visualiser.js";
  
  let startRadioBtn, startCallBtn, endCallBtn, textOutput;
  let ws = null;          // WebSocket for caller stream
  let hostWS = null;      // WebSocket for host (Matt/Mollie) TTS
  let audioContext = null;
  
  window.addEventListener("DOMContentLoaded", () => {
    startRadioBtn = document.getElementById("startRadioBtn");
    startCallBtn = document.getElementById("startCallBtn");
    endCallBtn = document.getElementById("endCallBtn");
    textOutput = document.getElementById("textOutput");
  
    startRadioBtn.addEventListener("click", doStartRadio);
    startCallBtn.addEventListener("click", startStreamFromServer);
    endCallBtn.addEventListener("click", stopStreamFromServer);
  
    // 1) Init the single host visualiser canvas
    initVisualiser();
  
    // 2) Periodically load queue from server
    loadQueue();
    setInterval(loadQueue, 1000);
  
    // 3) Open dedicated WebSocket for the radio hosts (Matt/Mollie) TTS
    startHostStream();
  });
  
  /**
   * POST /api/start_radio to start the station logic server-side
   */
  async function doStartRadio() {
    try {
      // If you want an AudioContext for local playback, create/resume it
      if (!audioContext) {
        audioContext = new AudioContext({ sampleRate: 24000 });
      }
      if (audioContext.state === "suspended") {
        await audioContext.resume();
      }
  
      const res = await fetch("/api/start_radio", { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        logText("Radio started: " + data.message);
        loadQueue();
      } else {
        logText("Error starting radio: " + JSON.stringify(data));
      }
    } catch (err) {
      logText("Error starting radio: " + err);
    }
  }
  
  /**
   * Periodically fetch the queue from server
   */
  async function loadQueue() {
    try {
      const res = await fetch("/api/queue");
      const data = await res.json();
      renderQueue(data.queue, data.currentIndex);
    } catch (err) {
      console.error("Failed to load queue:", err);
    }
  }
  
  /**
   * Render the queue in #queueContainer
   */
  function renderQueue(queueData, currentIdx) {
    const container = document.getElementById("queueContainer");
    container.innerHTML = "";
  
    queueData.forEach((item, idx) => {
      const div = document.createElement("div");
      div.classList.add("queue-item");
  
      // highlight the current item
      if (idx === currentIdx - 1) {
        div.classList.add("current");
      }
  
      if (item.type === "song") {
        div.classList.add("song");
        div.innerHTML = `<strong>Song</strong>: ${item.data.name} by ${item.data.artist}`;
      } else if (item.type === "conversation") {
        div.classList.add("conversation");
        const snippet = item.data.slice(0, 1).join(" / ");
        div.innerHTML = `<strong>Conversation</strong>: ${snippet}...`;
      } else if (item.type === "conversation_placeholder") {
        div.innerHTML = `<em>Conversation Placeholder</em>`;
      } else {
        div.innerHTML = `<strong>${item.type}</strong>`;
      }
  
      container.appendChild(div);
    });
  }
  
  /**
   * Start streaming PCM from the server – no mic usage (CALLER side).
   * We do NOT visualize the caller's audio.
   */
  function startStreamFromServer() {
    startCallBtn.disabled = true;
    endCallBtn.disabled = false;
    logText("Connecting to server for PCM streaming...");
    resetVisualiser();  // optional: clears the wave
  
    // Make sure we have an AudioContext for playback
    if (!audioContext) {
      audioContext = new AudioContext({ sampleRate: 24000 });
    }
    if (audioContext.state === "suspended") {
      audioContext.resume();
    }
  
    // Open WebSocket to server
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    ws = new WebSocket(`${protocol}//${host}/ws/realtime-convo`);
  
    ws.onopen = () => {
      logText("WebSocket connected to server (caller).");
    };
    ws.onerror = (e) => {
      logText("WebSocket error: " + JSON.stringify(e));
    };
    ws.onclose = () => {
      logText("WebSocket closed.");
      stopStreamFromServer();
    };
    ws.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch (err) {
        console.error("Non-JSON from server:", event.data);
        return;
      }
      handleCallerEvent(data);
    };
  }
  
  /**
   * End streaming from server
   */
  function stopStreamFromServer() {
    logText("Ending server stream...");
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.close();
    }
    cleanupStream();
  }
  
  /**
   * Cleanup caller side
   */
  function cleanupStream() {
    if (ws) {
      ws = null;
    }
    startCallBtn.disabled = false;
    endCallBtn.disabled = true;
    resetVisualiser();
  }
  
  /**
   * Handle events from the CALLER WebSocket
   * We do NOT visualize the caller's audio.
   */
  function handleCallerEvent(data) {
    switch (data.event) {
      case "media": {
        // data.media.payload is base64 of PCM16
        const b64 = data.media.payload;
        const raw = base64ToArrayBuffer(b64);
        // speaker is "caller" – no wave visualization for that
        playPCMChunk(raw);
        break;
      }
      case "text_delta": {
        if (data.delta) {
          logText("[AI partial] " + data.delta);
        }
        break;
      }
      case "text_done": {
        logText("[AI text done]");
        break;
      }
      default:
        break;
    }
  }
  
  /**
   * Start a dedicated WebSocket for host (Matt/Mollie) TTS
   * We DO visualize any chunk from 'matt' or 'mollie'
   */
  function startHostStream() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    hostWS = new WebSocket(`${protocol}//${host}/ws/host_audio`);
  
    hostWS.onopen = () => {
      console.log("Host TTS WebSocket connected!");
    };
    hostWS.onerror = (e) => {
      console.error("Host TTS WebSocket error:", e);
    };
    hostWS.onclose = () => {
      console.log("Host TTS WebSocket closed.");
    };
    hostWS.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch (err) {
        console.error("Host audio: non-JSON", event.data);
        return;
      }
  
      // Only handle "event=media" => PCM data
      if (data.event === "media" && data.media?.payload) {
        const raw = base64ToArrayBuffer(data.media.payload);
        const spk = (data.speaker || "matt").toLowerCase();
  
        // 1) Visualize ONLY if speaker is 'matt' or 'mollie'
        if (spk === "matt" || spk === "mollie") {
          updateVisualiser(new Uint8Array(raw), spk);
        }
  
        // 2) Always play out loud
        playPCMChunk(raw);
      }
    };
  }
  
  /**
   * Convert base64 -> ArrayBuffer
   */
  function base64ToArrayBuffer(b64) {
    const binary = atob(b64);
    const len = binary.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
  }
  
  /**
   * Play raw PCM16 in the browser by decoding it into an AudioBuffer
   */
  function playPCMChunk(rawPCM) {
    if (!audioContext) return;
  
    const dv = new DataView(rawPCM);
    const float32Samples = new Float32Array(dv.byteLength / 2);
  
    for (let i = 0, idx = 0; i < dv.byteLength; i += 2, idx++) {
      const int16 = dv.getInt16(i, true);
      float32Samples[idx] = Math.max(-1, Math.min(1, int16 / 32768));
    }
  
    const buffer = audioContext.createBuffer(1, float32Samples.length, 24000);
    buffer.copyToChannel(float32Samples, 0, 0);
  
    const source = audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(audioContext.destination);
    source.start();
  }
  
  /**
   * Logging utility
   */
  function logText(msg) {
    if (!textOutput) return;
    textOutput.textContent += msg + "\n";
    textOutput.scrollTop = textOutput.scrollHeight;
  }
  