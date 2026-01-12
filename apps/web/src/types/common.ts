export type JsonPrimitive = string | number | boolean | null
export type JsonArray = JsonValue[]
export interface JsonObject {
  [key: string]: JsonValue
}
export type JsonValue = JsonPrimitive | JsonObject | JsonArray

export type UnknownRecord = Record<string, unknown>
