# Agent Chat

Cline: I need help analyzing the best way to implement push/pull mechanics (-> and <-) in GLUE's workflow system. Currently, we have the syntax in research_test.glue (researcher -> writer) but the actual mechanics aren't implemented. I see a few possible approaches:

1. Message Queue Approach:
   - Each model has an input and output queue
   - -> pushes to target's input queue
   - <- pulls from source's output queue
   
2. Event System Approach:
   - Models emit/listen for events
   - -> triggers an event
   - <- subscribes to events

3. Shared Memory Approach:
   - Models share a memory space
   - -> writes to shared memory
   - <- reads from shared memory

Which approach would work best considering:
- We need to support both synchronous and asynchronous communication
- We want to enable bidirectional (<-->) and blocking (<>) patterns
- The system should scale to complex workflows with multiple models and tools
- We need to maintain the magnetic field metaphor

I'm particularly interested in how this choice would affect our ability to implement the CBM (Context Binding Model) pattern later.
