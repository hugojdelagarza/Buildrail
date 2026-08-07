// Prevents an additional console window from opening on Windows in release
// builds. Do not remove — this is required by Tauri's Windows packaging.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    buildrail_desktop_lib::run()
}
