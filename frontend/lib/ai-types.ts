// TS-Abbilder der lokalen-KI-DTOs (Backend app/ai/schemas).
// KEINE erfinderischen Zustände – nur das, was das Backend ehrlich meldet.
export interface AIStatus {
  provider: string;
  available: boolean;
  model: string;
  model_available: boolean;
  message: string;
}

export interface AITestResponse {
  provider: string;
  model: string;
  response: string | null;
  error: string | null;
}

export interface AITestRequest {
  text: string;
}

export type CapabilityBoolean = boolean | null;

export interface ModelCapabilities {
  text: CapabilityBoolean;
  vision: CapabilityBoolean;
  embedding: CapabilityBoolean;
}

export interface LocalModel {
  provider_id: string;
  model_id: string;
  display_name: string | null;
  state: "available" | "unavailable";
  loaded: boolean | null;
  context_length: number | null;
  quantization: string | null;
  family: string | null;
  parameter_size: string | null;
  capabilities: ModelCapabilities;
}

export type ProviderKind = "native" | "openai-compatible";

export interface ProviderInfo {
  provider_id: string;
  display_name: string;
  kind: ProviderKind;
  endpoint: string | null;
  reachable: boolean;
  detection: "native" | "openai-compatible" | null;
  message_de: string | null;
  models: LocalModel[];
}

export interface SelectionInfo {
  provider_id: string;
  model_id: string;
  source: "db" | "env";
  state: "ready" | "unavailable";
  provider_reachable: boolean;
  model_available: boolean;
  message_de: string;
}

export interface AISnapshot {
  selection: SelectionInfo;
  providers: ProviderInfo[];
  configured_default_provider: string;
  configured_default_model: string;
  application_version: string;
}

export interface SelectionUpdate {
  provider_id: string;
  model_id: string;
  endpoint?: string | null;
}