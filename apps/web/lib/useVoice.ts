"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { socketUrl, type Resource } from "./api";

const CAPTURE_RATE = 16_000;
const PLAYBACK_RATE = 24_000;

export type VoiceState = "loading" | "idle" | "recording" | "thinking" | "speaking";

export type Turn = {
  id: number;
  said: string;
  reply: string;
  crisis: boolean;
  resources: Resource[];
  timings?: { asr_ms: number; safety_ms: number; ttfa_ms: number | null };
};

// Captures raw frames from the microphone. Kept as a string so the whole
// client stays a static export with no extra file to serve.
const WORKLET = `
class Capture extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0][0];
    if (channel) this.port.postMessage(new Float32Array(channel));
    return true;
  }
}
registerProcessor("capture", Capture);
`;

function toInt16(samples: Float32Array): Int16Array {
  const out = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

export function useVoice(onTurnFinished: () => void) {
  const [state, setState] = useState<VoiceState>("loading");
  const [status, setStatus] = useState("Waking the models up. This takes a moment the first time.");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [askMood, setAskMood] = useState(false);

  const socket = useRef<WebSocket | null>(null);
  const capture = useRef<AudioContext | null>(null);
  const playback = useRef<AudioContext | null>(null);
  const micNode = useRef<AudioWorkletNode | null>(null);
  const micStream = useRef<MediaStream | null>(null);
  const sources = useRef<AudioBufferSourceNode[]>([]);
  const playHead = useRef(0);
  const stateRef = useRef<VoiceState>("loading");
  const nextId = useRef(0);

  const move = useCallback((next: VoiceState, message = "") => {
    stateRef.current = next;
    setState(next);
    setStatus(message);
  }, []);

  const stopPlayback = useCallback(() => {
    for (const source of sources.current) {
      try {
        source.stop();
      } catch {
        // already finished
      }
    }
    sources.current = [];
    playHead.current = 0;
  }, []);

  const play = useCallback(
    (bytes: ArrayBuffer) => {
      const context = playback.current;
      if (!context) return;
      const pcm = new Int16Array(bytes);
      const buffer = context.createBuffer(1, pcm.length, PLAYBACK_RATE);
      const channel = buffer.getChannelData(0);
      for (let i = 0; i < pcm.length; i++) channel[i] = pcm[i] / 32768;

      const source = context.createBufferSource();
      source.buffer = buffer;
      source.connect(context.destination);
      const startAt = Math.max(context.currentTime, playHead.current);
      source.start(startAt);
      playHead.current = startAt + buffer.duration;
      sources.current.push(source);
      source.onended = () => {
        sources.current = sources.current.filter((s) => s !== source);
        if (sources.current.length === 0 && stateRef.current === "speaking") {
          move("idle");
          setAskMood(true);
        }
      };
    },
    [move],
  );

  useEffect(() => {
    let cancelled = false;

    const connect = () => {
      const ws = new WebSocket(socketUrl());
      ws.binaryType = "arraybuffer";
      socket.current = ws;

      ws.onopen = () => move("idle");
      ws.onclose = () => {
        if (!cancelled) move("loading", "Disconnected.");
      };

      ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          move("speaking");
          play(event.data);
          return;
        }
        const message = JSON.parse(event.data);

        if (message.type === "transcript") {
          const id = ++nextId.current;
          setTurns((previous) => [
            { id, said: message.text, reply: "", crisis: false, resources: [] },
            ...previous,
          ]);
        } else if (message.type === "reply") {
          setTurns(([first, ...rest]) =>
            first ? [{ ...first, reply: `${first.reply} ${message.text}`.trim() }, ...rest] : [],
          );
        } else if (message.type === "crisis") {
          setTurns(([first, ...rest]) =>
            first
              ? [
                  { ...first, reply: message.text, crisis: true, resources: message.resources },
                  ...rest,
                ]
              : [],
          );
        } else if (message.type === "done") {
          setTurns(([first, ...rest]) =>
            first ? [{ ...first, timings: message.timings }, ...rest] : [],
          );
          if (sources.current.length === 0) move("idle");
          onTurnFinished();
        } else if (message.type === "error") {
          move("idle", message.message);
        }
      };
    };

    const waitForServer = async () => {
      for (let i = 0; i < 120 && !cancelled; i++) {
        try {
          const response = await fetch(`${process.env.NEXT_PUBLIC_API ?? ""}/health`);
          if ((await response.json()).ok) {
            connect();
            return;
          }
        } catch {
          // not up yet
        }
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
      if (!cancelled) setStatus("The server did not come up.");
    };

    void waitForServer();
    return () => {
      cancelled = true;
      socket.current?.close();
    };
  }, [move, play, onTurnFinished]);

  const startRecording = useCallback(async () => {
    if (!capture.current) {
      capture.current = new AudioContext({ sampleRate: CAPTURE_RATE });
      await capture.current.audioWorklet.addModule(
        URL.createObjectURL(new Blob([WORKLET], { type: "text/javascript" })),
      );
    }
    await capture.current.resume();
    micStream.current = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    });
    const node = new AudioWorkletNode(capture.current, "capture");
    node.port.onmessage = (event: MessageEvent<Float32Array>) => {
      if (stateRef.current === "recording" && socket.current?.readyState === WebSocket.OPEN) {
        socket.current.send(toInt16(event.data).buffer);
      }
    };
    capture.current.createMediaStreamSource(micStream.current).connect(node);
    micNode.current = node;
    setAskMood(false);
    move("recording", "Listening. Press again when you are done.");
  }, [move]);

  const stopRecording = useCallback(() => {
    micNode.current?.port.close();
    micNode.current?.disconnect();
    micStream.current?.getTracks().forEach((track) => track.stop());
    micNode.current = null;
    micStream.current = null;
  }, []);

  const press = useCallback(async () => {
    if (state === "idle") {
      playback.current ??= new AudioContext({ sampleRate: PLAYBACK_RATE });
      await playback.current.resume();
      await startRecording();
    } else if (state === "recording") {
      stopRecording();
      socket.current?.send(JSON.stringify({ type: "end" }));
      move("thinking");
    } else if (state === "speaking") {
      stopPlayback();
      socket.current?.send(JSON.stringify({ type: "stop" }));
      move("idle");
      setAskMood(true);
    }
  }, [state, startRecording, stopRecording, stopPlayback, move]);

  const setMood = useCallback((value: number) => {
    socket.current?.send(JSON.stringify({ type: "mood", value }));
  }, []);

  const clearTurns = useCallback(() => setTurns([]), []);

  return { state, status, turns, press, askMood, setMood, clearTurns };
}
