
So -> means that the researcher should be pushing information to the writer, or in other words the writer should be pulling (<-) information from the researcher... SO, why didnt it? Is this implemented? if so what went wrong? 

if not, is it worth it to implement?

can we define a difference between -> pushing and <- pulling? or is it the same concept working both ways that just adds to developer ease while testing different workflow binding configurations?

What happened to <--> when it came to configuring which assistants could talk with each other? Is that still implemented? again if so why arent we using it? if not, 

is it worth adding? 


repel (<>).. is this a good example of testing different workflow configurations? could blocking access between models and tools sometimes be more effective than allowing access between others? for example, if we make the researcher >< web_search, writer >< file_handler, writer <- web_search, researcher <> file_handler, researcher <--> writer, be more effective by allowing a more clear workflow design without being too rigid or restrictive? 

Agents. If we implement Agents into GLUE, to break prompts into smaller tasks, and delegate them to the models, or assistants, being able to utilize assistants the way the assistants (aka models) utilize tools? 
ls this a good time to implement the agent concept into the GLUE core? 

or is it best to make sure that assistants can run smaller apps alone, with tools? and once we know they can, THEN implement agents, to smooth out the context awareness, workflow conflicts, etc? 

To be truly Agentic, GLUE should be able to recognize if the task is headed for failure, because of a malfunctioning assistant or tool or something, and take a step back, reason through the problem and take a different approach, being able to catch errors and task failures. 

For this, reinforcement learning on chain-of-thought processing through few-shot self-reasoning, in a reAct tree-of-thoughts can be immensely powerful, but also it can be slower and harder to implement. 

so when it comes to that, how should we implement Agents? if we want to allow agents to be created outside of applications for modular use of pre-built agents in many different applications, how do we implement NLP and self-reasoning processes, reAct, etc? 

this is where a CBM (Conversational Based Model, or Context Binding Model) would be very helpful, as within the CBM a prompt chain could be used where one agent could use few-shot reasoning to give itself similar examples of the current task, then the prompt + response is sent to the next Agent which uses a tree-of-thoughts to attempt to account for unexpected errors or breakage, then prompt + response + response gets sent to the next model who could define a reAct response, and finally the fourth model would be able to use RFL prompting (please see the file 'RFL Prompting.md' in the root directory - RFL prompting is a new prompt engineering technique concept I have come up with, please read it), 

I do believe this prompt-chain concept and RFL prompting together within a CBM could be a very powerful new way of configuring and using AI Agents. 