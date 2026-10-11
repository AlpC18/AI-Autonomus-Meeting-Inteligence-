# Product Context

## Problem

Meeting tools produce text nobody acts on. People misquote past decisions, commitments are written down but never turned into tickets, and assistants know nothing about the codebase being discussed.

## What the product does

- **During the meeting:** a subtle HUD alert when a statement conflicts with the record, for example "In the Aug 14 meeting, the budget was revised down to $35k."
- **After the meeting:** proposes concrete actions (ticket, assignee, deadline, Slack notice) and executes them once the user approves.
- **For engineers:** links what is said to the code it affects ("`/services/payment` uses Paddle; Stripe touches 3 controllers").
- **Always:** remembers everything locally, per project, with no leakage between clients.

## UX goals

- The HUD must be non-intrusive: glanceable, dismissible, never blocks the meeting.
- Nothing leaves the machine or changes an external system without explicit approval.
- Human notes and live transcript blend in one notepad view.
