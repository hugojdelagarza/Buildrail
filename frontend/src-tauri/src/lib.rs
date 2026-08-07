// Hosts the existing React frontend in a native window. Deliberately has no
// Buildrail commands, state, or business logic — the frontend talks to the
// Python `buildrail serve` HTTP service directly, exactly as it does in a
// browser. See ../../docs/frontend.md for the architecture boundary.

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running the Buildrail desktop shell");
}
