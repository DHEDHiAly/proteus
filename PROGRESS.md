# Fix: Chat messages state initialization (P0)

## Problem
`messages` state in `AgentPage.tsx` could be undefined when component mounts, crashing the UI on render.

## Changes
- **frontend/src/pages/AgentPage.tsx**
  - Initialized `useState<AgentMessage[]>` with a default welcome message instead of empty array
  - Added null-safe access: `messages?.length` and `messages?.map(...)` in render
  - `useEffect` dependency on `messages` already used optional chaining on ref

## Testing
- TypeScript type check passes (`tsc --noEmit`)

## Status
- [x] messages state properly initialized
- [x] null-safe render access
- [x] type-check passes
