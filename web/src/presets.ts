import { RuntimeConfig, MappingRule } from './config-model';

function thrustmasterRule(
  productId: number,
  sourceControlId: string,
  targetControlId: string,
  transform?: any
): MappingRule {
  return {
    source_vendor_id: 0x044f,
    source_product_id: productId,
    source_interface_id: 0,
    source_control_id: sourceControlId,
    target_control_id: targetControlId,
    invert: false,
    deadzone: null,
    transform: transform || null,
  };
}

export const flightPackGeneric: RuntimeConfig = {
  schema_version: 1,
  metadata_version: 1,
  display_name: 'Flight Pack Generic',
  selected_persona: 'generic_gamepad',
  selected_profile: 'custom_runtime',
  bridge: {
    auto_start_persona: true,
    auto_start_bridge: false,
    rate_hz: 50,
  },
  mappings: [
    thrustmasterRule(0xb10a, 'axis_01_30', 'x'),
    thrustmasterRule(0xb10a, 'axis_01_31', 'y'),
    thrustmasterRule(0xb687, 'axis_01_32', 'z'),
    thrustmasterRule(0xb687, 'axis_01_36', 'rx'),
  ],
};

export const flightPackXbox: RuntimeConfig = {
  schema_version: 1,
  metadata_version: 1,
  display_name: 'Flight Pack Xbox',
  selected_persona: 'xbox_wireless_controller',
  selected_profile: 'custom_runtime',
  bridge: {
    auto_start_persona: true,
    auto_start_bridge: false,
    rate_hz: 50,
  },
  mappings: [
    thrustmasterRule(0xb10a, 'axis_01_30', 'left_x'),
    thrustmasterRule(0xb10a, 'axis_01_31', 'left_y'),
    thrustmasterRule(0xb10a, 'axis_01_36', 'right_x'),
    thrustmasterRule(0xb687, 'axis_01_32', 'right_trigger', {
      type: 'axis_to_trigger',
      source_min: -32768,
      source_max: 32767,
      invert: false,
    }),
    thrustmasterRule(0xb10a, 'hat_01_39', 'hat'),
    thrustmasterRule(0xb10a, 'button_1', 'a'),
    thrustmasterRule(0xb10a, 'button_2', 'b'),
    thrustmasterRule(0xb10a, 'button_3', 'x'),
    thrustmasterRule(0xb10a, 'button_4', 'y'),
  ],
};
