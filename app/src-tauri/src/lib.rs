//! Echlon desktop console — Tauri backend.
//!
//! The React webview never talks to the echlon daemon directly. Instead it goes
//! through these commands, so (a) WKWebView's cross-origin / CSP rules can never
//! block a local request, and (b) the Server-Sent-Events stream is parsed in one
//! well-tested place and pushed to the UI over a typed `Channel`.
//!
//! Daemon contract (see daemon/README.md):
//!   GET  /health                          -> {"status":"ok"}
//!   POST /run    {task, provider?, ...}    -> {"session_id": "..."}
//!   GET  /events?session=<id>             -> text/event-stream of {type, data}
//!   POST /approve {session, id, decision} -> {"ok": bool}

use std::time::Duration;

use futures_util::StreamExt;
use serde_json::Value;
use tauri::ipc::Channel;

/// Normalise a user-supplied base URL: trim trailing slashes so we can append
/// `/health` etc. without producing a double slash.
fn normalize_base(base: &str) -> &str {
    base.trim().trim_end_matches('/')
}

fn http_client(timeout: Duration) -> Result<reqwest::Client, String> {
    reqwest::Client::builder()
        .timeout(timeout)
        .build()
        .map_err(|e| format!("failed to build HTTP client: {e}"))
}

/// `GET /health` — returns true only when the daemon answers `{"status":"ok"}`.
#[tauri::command]
async fn daemon_health(base: String) -> Result<bool, String> {
    let client = http_client(Duration::from_secs(4))?;
    let url = format!("{}/health", normalize_base(&base));
    let resp = client
        .get(&url)
        .send()
        .await
        .map_err(|e| format!("{e}"))?;
    if !resp.status().is_success() {
        return Ok(false);
    }
    let body: Value = resp.json().await.map_err(|e| format!("{e}"))?;
    Ok(body.get("status").and_then(Value::as_str) == Some("ok"))
}

/// `POST /run` — starts a task, returns the new session id.
#[tauri::command]
async fn start_task(base: String, payload: Value) -> Result<String, String> {
    let client = http_client(Duration::from_secs(15))?;
    let url = format!("{}/run", normalize_base(&base));
    let resp = client
        .post(&url)
        .json(&payload)
        .send()
        .await
        .map_err(|e| format!("could not reach the daemon: {e}"))?;
    let status = resp.status();
    let body: Value = resp
        .json()
        .await
        .map_err(|e| format!("daemon returned a non-JSON response: {e}"))?;
    if !status.is_success() {
        let msg = body
            .get("error")
            .and_then(Value::as_str)
            .unwrap_or("unknown error");
        return Err(format!("daemon rejected the task ({status}): {msg}"));
    }
    body.get("session_id")
        .and_then(Value::as_str)
        .map(str::to_owned)
        .ok_or_else(|| "daemon did not return a session_id".to_string())
}

/// `POST /message` — send a message to an open session (new turn, or steers a
/// running turn). Returns the daemon's `{ok, mode}` body.
#[tauri::command]
async fn send_message(base: String, session: String, text: String) -> Result<Value, String> {
    let client = http_client(Duration::from_secs(15))?;
    let url = format!("{}/message", normalize_base(&base));
    let resp = client
        .post(&url)
        .json(&serde_json::json!({ "session": session, "text": text }))
        .send()
        .await
        .map_err(|e| format!("could not reach the daemon: {e}"))?;
    let status = resp.status();
    let body: Value = resp.json().await.map_err(|e| format!("{e}"))?;
    if !status.is_success() {
        let msg = body.get("error").and_then(Value::as_str).unwrap_or("unknown error");
        return Err(format!("daemon rejected the message ({status}): {msg}"));
    }
    Ok(body)
}

/// `POST /cancel` — cancel the in-progress turn (the session stays open).
#[tauri::command]
async fn cancel_turn(base: String, session: String) -> Result<bool, String> {
    let client = http_client(Duration::from_secs(10))?;
    let url = format!("{}/cancel", normalize_base(&base));
    let resp = client
        .post(&url)
        .json(&serde_json::json!({ "session": session }))
        .send()
        .await
        .map_err(|e| format!("could not reach the daemon: {e}"))?;
    let body: Value = resp.json().await.map_err(|e| format!("{e}"))?;
    Ok(body.get("ok").and_then(Value::as_bool).unwrap_or(false))
}

/// `POST /close` — end the conversation/session.
#[tauri::command]
async fn close_session(base: String, session: String) -> Result<bool, String> {
    let client = http_client(Duration::from_secs(10))?;
    let url = format!("{}/close", normalize_base(&base));
    let resp = client
        .post(&url)
        .json(&serde_json::json!({ "session": session }))
        .send()
        .await
        .map_err(|e| format!("could not reach the daemon: {e}"))?;
    let body: Value = resp.json().await.map_err(|e| format!("{e}"))?;
    Ok(body.get("ok").and_then(Value::as_bool).unwrap_or(false))
}

/// `POST /approve` — answer a pending approval (`once` | `always` | `deny`).
#[tauri::command]
async fn approve(
    base: String,
    session: String,
    id: String,
    decision: String,
) -> Result<bool, String> {
    let client = http_client(Duration::from_secs(10))?;
    let url = format!("{}/approve", normalize_base(&base));
    let resp = client
        .post(&url)
        .json(&serde_json::json!({ "session": session, "id": id, "decision": decision }))
        .send()
        .await
        .map_err(|e| format!("could not reach the daemon: {e}"))?;
    let body: Value = resp.json().await.map_err(|e| format!("{e}"))?;
    Ok(body.get("ok").and_then(Value::as_bool).unwrap_or(false))
}

/// `GET /events?session=<id>` — open the SSE stream and forward each parsed
/// event object to the UI over `on_event`. Resolves when the stream closes;
/// a final `{"type":"__closed"}` marker is always sent so the UI can settle its
/// state even if the daemon drops the connection without a `done` event.
#[tauri::command]
async fn stream_events(
    base: String,
    session: String,
    on_event: Channel<Value>,
) -> Result<(), String> {
    // No client timeout: an event stream is intentionally long-lived.
    let client = reqwest::Client::builder()
        .build()
        .map_err(|e| format!("failed to build HTTP client: {e}"))?;
    let url = format!(
        "{}/events?session={}",
        normalize_base(&base),
        urlencoding(&session)
    );
    let resp = client
        .get(&url)
        .header("Accept", "text/event-stream")
        .send()
        .await
        .map_err(|e| format!("could not open the event stream: {e}"))?;

    if !resp.status().is_success() {
        let _ = on_event.send(serde_json::json!({ "type": "__closed" }));
        return Err(format!("event stream returned {}", resp.status()));
    }

    let mut stream = resp.bytes_stream();
    let mut buf: Vec<u8> = Vec::new();

    while let Some(chunk) = stream.next().await {
        let bytes = match chunk {
            Ok(b) => b,
            Err(e) => {
                let _ = on_event.send(serde_json::json!({ "type": "__closed" }));
                return Err(format!("event stream error: {e}"));
            }
        };
        buf.extend_from_slice(&bytes);

        // SSE frames are newline-delimited; the daemon emits one JSON object per
        // `data:` line. Splitting on the newline byte is UTF-8 safe (0x0A never
        // appears inside a multi-byte sequence).
        while let Some(pos) = buf.iter().position(|&b| b == b'\n') {
            let line: Vec<u8> = buf.drain(..=pos).collect();
            let line = String::from_utf8_lossy(&line);
            let line = line.trim();
            if let Some(data) = line.strip_prefix("data:") {
                let data = data.trim();
                if !data.is_empty() {
                    if let Ok(value) = serde_json::from_str::<Value>(data) {
                        let _ = on_event.send(value);
                    }
                }
            }
        }
    }

    let _ = on_event.send(serde_json::json!({ "type": "__closed" }));
    Ok(())
}

/// Minimal percent-encoding for the session id (hex from the daemon, but be safe).
fn urlencoding(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for b in s.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                out.push(b as char)
            }
            _ => out.push_str(&format!("%{b:02X}")),
        }
    }
    out
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            daemon_health,
            start_task,
            send_message,
            cancel_turn,
            close_session,
            approve,
            stream_events
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
