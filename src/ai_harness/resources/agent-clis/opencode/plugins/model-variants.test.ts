import { test, expect } from "bun:test"
import { extractVariants } from "./model-variants"

test("extracts variant keys per model, sorted", () => {
  const providerList = [
    {
      id: "anthropic",
      models: {
        "claude-opus": { variants: { high: {}, low: {}, medium: {} } },
      },
    },
  ]

  expect(extractVariants(providerList)).toEqual({
    anthropic: { "claude-opus": ["high", "low", "medium"] },
  })
})

test("skips models that have no variants", () => {
  const providerList = [
    {
      id: "anthropic",
      models: {
        "claude-opus": { variants: { high: {} } },
        "claude-haiku": {},
        "claude-sonnet": { variants: {} },
      },
    },
  ]

  expect(extractVariants(providerList)).toEqual({
    anthropic: { "claude-opus": ["high"] },
  })
})

test("returns empty result when no model has variants", () => {
  const providerList = [
    {
      id: "anthropic",
      models: {
        "claude-haiku": {},
        "claude-sonnet": { variants: {} },
      },
    },
  ]

  expect(extractVariants(providerList)).toEqual({})
})

test("returns empty result for providers with missing models", () => {
  const providerList = [{ id: "anthropic" }, { id: "openai", models: {} }]

  expect(extractVariants(providerList)).toEqual({})
})

test("collects variants across multiple providers", () => {
  const providerList = [
    {
      id: "anthropic",
      models: {
        "claude-opus": { variants: { high: {}, low: {} } },
      },
    },
    {
      id: "openai",
      models: {
        "gpt-5": { variants: { minimal: {}, xhigh: {} } },
        "gpt-4": {},
      },
    },
  ]

  expect(extractVariants(providerList)).toEqual({
    anthropic: { "claude-opus": ["high", "low"] },
    openai: { "gpt-5": ["minimal", "xhigh"] },
  })
})
