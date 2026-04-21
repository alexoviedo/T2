//! usb2ble-app
//!
//! Responsible for orchestration and application state.

use usb2ble_contracts::{
    AppState, BleLinkState, BondStore, CONTRACT_VERSION, ControlCommand, ControlResponse,
    InfoResponse, ProfileResponse, ProfileStore, StatusResponse,
};

/// The main application structure.
pub struct App<S> {
    state: AppState,
    storage: S,
}

impl<S> App<S>
where
    S: ProfileStore + BondStore,
{
    /// Create a new application instance.
    pub fn new(storage: S) -> Self {
        let active_profile = storage.load_active_profile().ok().flatten();

        Self {
            state: AppState {
                known_devices: Vec::new(),
                descriptors: Vec::new(),
                active_profile,
                active_persona: None,
                ble_state: BleLinkState::Idle,
            },
            storage,
        }
    }

    /// Process a control plane command.
    pub fn handle_control_command(&mut self, cmd: ControlCommand) -> ControlResponse {
        match cmd {
            ControlCommand::GetInfo => ControlResponse::Info(InfoResponse {
                contract_version: CONTRACT_VERSION,
                firmware_name: "usb2ble",
                active_persona: self.state.active_persona,
            }),
            ControlCommand::GetStatus => {
                let bonds_present = self.storage.bonds_present().unwrap_or(false);
                ControlResponse::Status(StatusResponse {
                    ble_state: self.state.ble_state,
                    active_profile: self.state.active_profile,
                    bonds_present,
                })
            }
            ControlCommand::GetProfile => ControlResponse::Profile(ProfileResponse {
                active_profile: self.state.active_profile,
            }),
        }
    }

    /// Set the BLE state (e.g. from platform glue).
    pub fn set_ble_state(&mut self, state: BleLinkState) {
        self.state.ble_state = state;
    }

    /// Get current app state (read-only).
    #[must_use]
    pub fn state(&self) -> &AppState {
        &self.state
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use usb2ble_contracts::ProfileId;
    use usb2ble_storage::InMemoryStore;

    #[test]
    fn test_handle_get_info() {
        let storage = InMemoryStore::new();
        let mut app = App::new(storage);
        let resp = app.handle_control_command(ControlCommand::GetInfo);

        if let ControlResponse::Info(info) = resp {
            assert_eq!(info.contract_version, CONTRACT_VERSION);
            assert_eq!(info.firmware_name, "usb2ble");
        } else {
            panic!("Expected Info response");
        }
    }

    #[test]
    fn test_handle_get_status() {
        let mut storage = InMemoryStore::new();
        let profile = ProfileId("test-profile");
        storage.save_active_profile(profile).unwrap();

        let mut app = App::new(storage);
        app.set_ble_state(BleLinkState::Connected);

        let resp = app.handle_control_command(ControlCommand::GetStatus);

        if let ControlResponse::Status(status) = resp {
            assert_eq!(status.ble_state, BleLinkState::Connected);
            assert_eq!(status.active_profile, Some(profile));
            assert!(!status.bonds_present);
        } else {
            panic!("Expected Status response");
        }
    }
}
