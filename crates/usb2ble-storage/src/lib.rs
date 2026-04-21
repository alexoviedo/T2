//! usb2ble-storage
//!
//! Responsible for:
//! - profile persistence traits,
//! - bond persistence traits,
//! - config persistence traits,
//! - host-memory implementations for testing.

use std::sync::{Arc, Mutex};
use usb2ble_contracts::{
    BondStore, ConfigStore, ProfileId, ProfileStore, RuntimeConfig, StoreError,
};

/// In-memory implementation of project storage traits for testing and host-replay.
#[derive(Default, Clone)]
pub struct InMemoryStore {
    active_profile: Arc<Mutex<Option<ProfileId>>>,
    config: Arc<Mutex<Option<RuntimeConfig>>>,
    bonds: Arc<Mutex<bool>>,
}

impl InMemoryStore {
    /// Creates a new empty in-memory store.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }
}

impl ProfileStore for InMemoryStore {
    fn load_active_profile(&self) -> Result<Option<ProfileId>, StoreError> {
        Ok(*self.active_profile.lock().unwrap())
    }

    fn save_active_profile(&mut self, profile: ProfileId) -> Result<(), StoreError> {
        *self.active_profile.lock().unwrap() = Some(profile);
        Ok(())
    }
}

impl ConfigStore for InMemoryStore {
    fn load_config(&self) -> Result<Option<RuntimeConfig>, StoreError> {
        Ok(self.config.lock().unwrap().clone())
    }

    fn save_config(&mut self, config: &RuntimeConfig) -> Result<(), StoreError> {
        *self.config.lock().unwrap() = Some(config.clone());
        Ok(())
    }
}

impl BondStore for InMemoryStore {
    fn bonds_present(&self) -> Result<bool, StoreError> {
        Ok(*self.bonds.lock().unwrap())
    }

    fn clear_bonds(&mut self) -> Result<(), StoreError> {
        *self.bonds.lock().unwrap() = false;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use usb2ble_contracts::ProfileId;

    #[test]
    fn test_profile_store() {
        let mut store = InMemoryStore::new();
        assert_eq!(store.load_active_profile().unwrap(), None);

        let profile = ProfileId("test_profile");
        store.save_active_profile(profile).unwrap();
        assert_eq!(store.load_active_profile().unwrap(), Some(profile));
    }

    #[test]
    fn test_config_store() {
        let mut store = InMemoryStore::new();
        assert!(store.load_config().unwrap().is_none());

        let config = RuntimeConfig {};
        store.save_config(&config).unwrap();
        assert!(store.load_config().unwrap().is_some());
    }

    #[test]
    fn test_bond_store() {
        let mut store = InMemoryStore::new();
        // In this mock, let's say we can't "set" bonds easily without a back door
        // but we can clear them.
        assert!(!store.bonds_present().unwrap());
        *store.bonds.lock().unwrap() = true;
        assert!(store.bonds_present().unwrap());
        store.clear_bonds().unwrap();
        assert!(!store.bonds_present().unwrap());
    }
}
