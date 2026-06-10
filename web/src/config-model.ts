export interface Transform {
  type: string;
  source_min?: number;
  source_max?: number;
  invert?: boolean;
}

export interface MappingRule {
  source_vendor_id: number;
  source_product_id: number;
  source_interface_id?: number | null;
  source_control_id: string;
  target_control_id: string;
  invert: boolean;
  deadzone?: number | null;
  transform?: Transform | null;
}

export interface BridgeConfig {
  auto_start_persona: boolean;
  auto_start_bridge: boolean;
  rate_hz: number;
}

export interface StartupBleConfig {
  enabled: boolean;
  persona: 'generic_gamepad' | 'xbox_wireless_controller';
  identity_strategy: 'legacy_public' | 'persona_static_random_experimental';
  compatibility_variant: 'generic_default' | 'generic_hogp_strict' | 'generic_unsigned_6axis' | 'xbox_compatibility';
}

export interface RuntimeConfig {
  schema_version: number;
  metadata_version: number;
  display_name: string;
  selected_persona: 'generic_gamepad' | 'xbox_wireless_controller';
  selected_profile: string;
  bridge: BridgeConfig;
  startup_ble?: StartupBleConfig;
  mappings: MappingRule[];
}
