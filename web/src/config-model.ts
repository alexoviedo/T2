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

export interface RuntimeConfig {
  schema_version: number;
  metadata_version: number;
  display_name: string;
  selected_persona: 'generic_gamepad' | 'xbox_wireless_controller';
  selected_profile: string;
  bridge: BridgeConfig;
  mappings: MappingRule[];
}
