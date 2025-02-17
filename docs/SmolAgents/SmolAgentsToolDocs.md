

[](#tools)Tools
---------------

A tool is an atomic function to be used by an agent. To be used by an LLM, it also needs a few attributes that constitute its API and will be used to describe to the LLM how to call this tool:

*   A name
*   A description
*   Input types and descriptions
*   An output type

You can for instance check the [PythonInterpreterTool](/docs/smolagents/v1.7.0/en/reference/tools#smolagents.PythonInterpreterTool): it has a name, a description, input descriptions, an output type, and a `forward` method to perform the action.

When the agent is initialized, the tool attributes are used to generate a tool description which is baked into the agent’s system prompt. This lets the agent know which tools it can use and why.

### [](#default-toolbox)Default toolbox

Transformers comes with a default toolbox for empowering agents, that you can add to your agent upon initialization with argument `add_base_tools = True`:

*   **DuckDuckGo web search\***: performs a web search using DuckDuckGo browser.
*   **Python code interpreter**: runs your LLM generated Python code in a secure environment. This tool will only be added to [ToolCallingAgent](/docs/smolagents/v1.7.0/en/reference/agents#smolagents.ToolCallingAgent) if you initialize it with `add_base_tools=True`, since code-based agent can already natively execute Python code
*   **Transcriber**: a speech-to-text pipeline built on Whisper-Turbo that transcribes an audio to text.

You can manually use a tool by calling it with its arguments.

Copied

from smolagents import DuckDuckGoSearchTool

search\_tool = DuckDuckGoSearchTool()
print(search\_tool("Who's the current president of Russia?"))

### [](#create-a-new-tool)Create a new tool

You can create your own tool for use cases not covered by the default tools from Hugging Face. For example, let’s create a tool that returns the most downloaded model for a given task from the Hub.

You’ll start with the code below.

Copied

from huggingface\_hub import list\_models

task = "text-classification"

most\_downloaded\_model = next(iter(list\_models(filter\=task, sort="downloads", direction=-1)))
print(most\_downloaded\_model.id)

This code can quickly be converted into a tool, just by wrapping it in a function and adding the `tool` decorator: This is not the only way to build the tool: you can directly define it as a subclass of [Tool](/docs/smolagents/v1.7.0/en/reference/tools#smolagents.Tool), which gives you more flexibility, for instance the possibility to initialize heavy class attributes.

Let’s see how it works for both options:

Decorate a function with @tool

Subclass Tool

Copied

from smolagents import tool

@tool
def model\_download\_tool(task: str) -> str:
    """
    This is a tool that returns the most downloaded model of a given task on the Hugging Face Hub.
    It returns the name of the checkpoint.

    Args:
        task: The task for which to get the download count.
    """
    most\_downloaded\_model = next(iter(list\_models(filter\=task, sort="downloads", direction=-1)))
    return most\_downloaded\_model.id

The function needs:

*   A clear name. The name should be descriptive enough of what this tool does to help the LLM brain powering the agent. Since this tool returns the model with the most downloads for a task, let’s name it `model_download_tool`.
*   Type hints on both inputs and output
*   A description, that includes an ‘Args:’ part where each argument is described (without a type indication this time, it will be pulled from the type hint). Same as for the tool name, this description is an instruction manual for the LLM powering you agent, so do not neglect it. All these elements will be automatically baked into the agent’s system prompt upon initialization: so strive to make them as clear as possible!

This definition format is the same as tool schemas used in `apply_chat_template`, the only difference is the added `tool` decorator: read more on our tool use API [here](https://huggingface.co/blog/unified-tool-use#passing-tools-to-a-chat-template).

Then you can directly initialize your agent:

Copied

from smolagents import CodeAgent, HfApiModel
agent = CodeAgent(tools=\[model\_download\_tool\], model=HfApiModel())
agent.run(
    "Can you give me the name of the model that has the most downloads in the 'text-to-video' task on the Hugging Face Hub?"
)

You get the following logs:

Copied

╭──────────────────────────────────────── New run ─────────────────────────────────────────╮
│                                                                                          │
│ Can you give me the name of the model that has the most downloads in the 'text-to-video' │
│ task on the Hugging Face Hub?                                                            │
│                                                                                          │
╰─ HfApiModel - Qwen/Qwen2.5-Coder-32B-Instruct ───────────────────────────────────────────╯
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ Step 0 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
╭─ Executing this code: ───────────────────────────────────────────────────────────────────╮
│   1 model\_name = model\_download\_tool(task="text-to-video")                               │
│   2 print(model\_name)                                                                    │
╰──────────────────────────────────────────────────────────────────────────────────────────╯
Execution logs:
ByteDance/AnimateDiff-Lightning

Out: None
\[Step 0: Duration 0.27 seconds| Input tokens: 2,069 | Output tokens: 60\]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ Step 1 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
╭─ Executing this code: ───────────────────────────────────────────────────────────────────╮
│   1 final\_answer("ByteDance/AnimateDiff-Lightning")                                      │
╰──────────────────────────────────────────────────────────────────────────────────────────╯
Out - Final answer: ByteDance/AnimateDiff-Lightning
\[Step 1: Duration 0.10 seconds| Input tokens: 4,288 | Output tokens: 148\]
Out\[20\]: 'ByteDance/AnimateDiff-Lightning'

Read more on tools in the [dedicated tutorial](./tutorials/tools#what-is-a-tool-and-how-to-build-one).

## [](#best-practices-for-building-agents)Best practices for building agents

There’s a world of difference between building an agent that works and one that doesn’t. How can we build agents that fall into the latter category? In this guide, we’re going to talk about best practices for building agents.



### [](#the-best-agentic-systems-are-the-simplest-simplify-the-workflow-as-much-as-you-can)The best agentic systems are the simplest: simplify the workflow as much as you can

Giving an LLM some agency in your workflow introduces some risk of errors.

Well-programmed agentic systems have good error logging and retry mechanisms anyway, so the LLM engine has a chance to self-correct their mistake. But to reduce the risk of LLM error to the maximum, you should simplify your workflow!

Let’s revisit the example from the [intro to agents](../conceptual_guides/intro_agents): a bot that answers user queries for a surf trip company. Instead of letting the agent do 2 different calls for “travel distance API” and “weather API” each time they are asked about a new surf spot, you could just make one unified tool “return\_spot\_information”, a function that calls both APIs at once and returns their concatenated outputs to the user.

This will reduce costs, latency, and error risk!

The main guideline is: Reduce the number of LLM calls as much as you can.

This leads to a few takeaways:

*   Whenever possible, group 2 tools in one, like in our example of the two APIs.
*   Whenever possible, logic should be based on deterministic functions rather than agentic decisions.

### [](#improve-the-information-flow-to-the-llm-engine)Improve the information flow to the LLM engine

Remember that your LLM engine is like an _intelligent_ robot, tapped into a room with the only communication with the outside world being notes passed under a door.

It won’t know of anything that happened if you don’t explicitly put that into its prompt.

So first start with making your task very clear! Since an agent is powered by an LLM, minor variations in your task formulation might yield completely different results.

Then, improve the information flow towards your agent in tool use.

Particular guidelines to follow:

*   Each tool should log (by simply using `print` statements inside the tool’s `forward` method) everything that could be useful for the LLM engine.
    *   In particular, logging detail on tool execution errors would help a lot!

For instance, here’s a tool that retrieves weather data based on location and date-time:

First, here’s a poor version:

Copied

import datetime
from smolagents import tool

def get\_weather\_report\_at\_coordinates(coordinates, date\_time):
    \# Dummy function, returns a list of \[temperature in °C, risk of rain on a scale 0-1, wave height in m\]
    return \[28.0, 0.35, 0.85\]

def convert\_location\_to\_coordinates(location):
    \# Returns dummy coordinates
    return \[3.3, -42.0\]

@tool
def get\_weather\_api(location: str, date\_time: str) -> str:
    """
    Returns the weather report.

    Args:
        location: the name of the place that you want the weather for.
        date\_time: the date and time for which you want the report.
    """
    lon, lat = convert\_location\_to\_coordinates(location)
    date\_time = datetime.strptime(date\_time)
    return str(get\_weather\_report\_at\_coordinates((lon, lat), date\_time))

Why is it bad?

*   there’s no precision of the format that should be used for `date_time`
*   there’s no detail on how location should be specified.
*   there’s no logging mechanism trying to make explicit failure cases like location not being in a proper format, or date\_time not being properly formatted.
*   the output format is hard to understand

If the tool call fails, the error trace logged in memory can help the LLM reverse engineer the tool to fix the errors. But why leave it with so much heavy lifting to do?

A better way to build this tool would have been the following:

Copied

@tool
def get\_weather\_api(location: str, date\_time: str) -> str:
    """
    Returns the weather report.

    Args:
        location: the name of the place that you want the weather for. Should be a place name, followed by possibly a city name, then a country, like "Anchor Point, Taghazout, Morocco".
        date\_time: the date and time for which you want the report, formatted as '%m/%d/%y %H:%M:%S'.
    """
    lon, lat = convert\_location\_to\_coordinates(location)
    try:
        date\_time = datetime.strptime(date\_time)
    except Exception as e:
        raise ValueError("Conversion of \`date\_time\` to datetime format failed, make sure to provide a string in format '%m/%d/%y %H:%M:%S'. Full trace:" + str(e))
    temperature\_celsius, risk\_of\_rain, wave\_height = get\_weather\_report\_at\_coordinates((lon, lat), date\_time)
    return f"Weather report for {location}, {date\_time}: Temperature will be {temperature\_celsius}°C, risk of rain is {risk\_of\_rain\*100:.0f}%, wave height is {wave\_height}m."

In general, to ease the load on your LLM, the good question to ask yourself is: “How easy would it be for me, if I was dumb and using this tool for the first time ever, to program with this tool and correct my own errors?“.

### [](#give-more-arguments-to-the-agent)Give more arguments to the agent

To pass some additional objects to your agent beyond the simple string describing the task, you can use the `additional_args` argument to pass any type of object:

Copied

from smolagents import CodeAgent, HfApiModel

model\_id = "meta-llama/Llama-3.3-70B-Instruct"

agent = CodeAgent(tools=\[\], model=HfApiModel(model\_id=model\_id), add\_base\_tools=True)

agent.run(
    "Why does Mike not know many people in New York?",
    additional\_args={"mp3\_sound\_file\_url":'https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/transformers/recording.mp3'}
)

For instance, you can use this `additional_args` argument to pass images or strings that you want your agent to leverage.

[](#how-to-debug-your-agent)How to debug your agent
---------------------------------------------------

### [](#1-use-a-stronger-llm)1\. Use a stronger LLM

In an agentic workflows, some of the errors are actual errors, some other are the fault of your LLM engine not reasoning properly. For instance, consider this trace for an `CodeAgent` that I asked to create a car picture:

Copied

\==================================================================================================== New task ====================================================================================================
Make me a cool car picture
──────────────────────────────────────────────────────────────────────────────────────────────────── New step ────────────────────────────────────────────────────────────────────────────────────────────────────
Agent is executing the code below: ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
image\_generator(prompt="A cool, futuristic sports car with LED headlights, aerodynamic design, and vibrant color, high-res, photorealistic")
──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

Last output from code snippet: ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
/var/folders/6m/9b1tts6d5w960j80wbw9tx3m0000gn/T/tmpx09qfsdd/652f0007-3ee9-44e2-94ac-90dae6bb89a4.png
Step 1:

- Time taken: 16.35 seconds
- Input tokens: 1,383
- Output tokens: 77
──────────────────────────────────────────────────────────────────────────────────────────────────── New step ────────────────────────────────────────────────────────────────────────────────────────────────────
Agent is executing the code below: ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
final\_answer("/var/folders/6m/9b1tts6d5w960j80wbw9tx3m0000gn/T/tmpx09qfsdd/652f0007-3ee9-44e2-94ac-90dae6bb89a4.png")
──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
Print outputs:

Last output from code snippet: ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
/var/folders/6m/9b1tts6d5w960j80wbw9tx3m0000gn/T/tmpx09qfsdd/652f0007-3ee9-44e2-94ac-90dae6bb89a4.png
Final answer:
/var/folders/6m/9b1tts6d5w960j80wbw9tx3m0000gn/T/tmpx09qfsdd/652f0007-3ee9-44e2-94ac-90dae6bb89a4.png

The user sees, instead of an image being returned, a path being returned to them. It could look like a bug from the system, but actually the agentic system didn’t cause the error: it’s just that the LLM brain did the mistake of not saving the image output into a variable. Thus it cannot access the image again except by leveraging the path that was logged while saving the image, so it returns the path instead of an image.

The first step to debugging your agent is thus “Use a more powerful LLM”. Alternatives like `Qwen2/5-72B-Instruct` wouldn’t have made that mistake.

### [](#2-provide-more-guidance--more-information)2\. Provide more guidance / more information

You can also use less powerful models, provided you guide them more effectively.

Put yourself in the shoes of your model: if you were the model solving the task, would you struggle with the information available to you (from the system prompt + task formulation + tool description) ?

Would you need some added clarifications?

To provide extra information, we do not recommend to change the system prompt right away: the default system prompt has many adjustments that you do not want to mess up except if you understand the prompt very well. Better ways to guide your LLM engine are:

*   If it’s about the task to solve: add all these details to the task. The task could be 100s of pages long.
*   If it’s about how to use tools: the description attribute of your tools.

### [](#3-change-the-system-prompt-generally-not-advised)3\. Change the system prompt (generally not advised)

If above clarifications are not sufficient, you can change the system prompt.

Let’s see how it works. For example, let us check the default system prompt for the [CodeAgent](/docs/smolagents/v1.7.0/en/reference/agents#smolagents.CodeAgent) (below version is shortened by skipping zero-shot examples).

Copied

print(agent.system\_prompt\_template)

Here is what you get:

Copied

You are an expert assistant who can solve any task using code blobs. You will be given a task to solve as best you can.
To do so, you have been given access to a list of tools: these tools are basically Python functions which you can call with code.
To solve the task, you must plan forward to proceed in a series of steps, in a cycle of 'Thought:', 'Code:', and 'Observation:' sequences.

At each step, in the 'Thought:' sequence, you should first explain your reasoning towards solving the task and the tools that you want to use.
Then in the 'Code:' sequence, you should write the code in simple Python. The code sequence must end with '<end\_code>' sequence.
During each intermediate step, you can use 'print()' to save whatever important information you will then need.
These print outputs will then appear in the 'Observation:' field, which will be available as input for the next step.
In the end you have to return a final answer using the \`final\_answer\` tool.

Here are a few examples using notional tools:
---
{examples}

Above example were using notional tools that might not exist for you. On top of performing computations in the Python code snippets that you create, you only have access to these tools:

{{tool\_descriptions}}

{{managed\_agents\_descriptions}}

Here are the rules you should always follow to solve your task:
1. Always provide a 'Thought:' sequence, and a 'Code:\\n\`\`\`py' sequence ending with '\`\`\`<end\_code>' sequence, else you will fail.
2. Use only variables that you have defined!
3. Always use the right arguments for the tools. DO NOT pass the arguments as a dict as in 'answer = wiki({'query': "What is the place where James Bond lives?"})', but use the arguments directly as in 'answer = wiki(query="What is the place where James Bond lives?")'.
4. Take care to not chain too many sequential tool calls in the same code block, especially when the output format is unpredictable. For instance, a call to search has an unpredictable return format, so do not have another tool call that depends on its output in the same block: rather output results with print() to use them in the next block.
5. Call a tool only when needed, and never re-do a tool call that you previously did with the exact same parameters.
6. Don't name any new variable with the same name as a tool: for instance don't name a variable 'final\_answer'.
7. Never create any notional variables in our code, as having these in your logs might derail you from the true variables.
8. You can use imports in your code, but only from the following list of modules: {{authorized\_imports}}
9. The state persists between code executions: so if in one step you've created variables or imported modules, these will all persist.
10. Don't give up! You're in charge of solving the task, not providing directions to solve it.

Now Begin! If you solve the task correctly, you will receive a reward of $1,000,000.

As you can see, there are placeholders like `"{{tool_descriptions}}"`: these will be used upon agent initialization to insert certain automatically generated descriptions of tools or managed agents.

So while you can overwrite this system prompt template by passing your custom prompt as an argument to the `system_prompt` parameter, your new system prompt must contain the following placeholders:

*   `"{{tool_descriptions}}"` to insert tool descriptions.
*   `"{{managed_agents_description}}"` to insert the description for managed agents if there are any.
*   For `CodeAgent` only: `"{{authorized_imports}}"` to insert the list of authorized imports.

Then you can change the system prompt as follows:

Copied

from smolagents.prompts import CODE\_SYSTEM\_PROMPT

modified\_system\_prompt = CODE\_SYSTEM\_PROMPT + "\\nHere you go!" \# Change the system prompt here

agent = CodeAgent(
    tools=\[\], 
    model=HfApiModel(), 
    system\_prompt=modified\_system\_prompt
)

This also works with the [ToolCallingAgent](/docs/smolagents/v1.7.0/en/reference/agents#smolagents.ToolCallingAgent).

### [](#4-extra-planning)4\. Extra planning

We provide a model for a supplementary planning step, that an agent can run regularly in-between normal action steps. In this step, there is no tool call, the LLM is simply asked to update a list of facts it knows and to reflect on what steps it should take next based on those facts.

Copied

from smolagents import load\_tool, CodeAgent, HfApiModel, DuckDuckGoSearchTool
from dotenv import load\_dotenv

load\_dotenv()

\# Import tool from Hub
image\_generation\_tool = load\_tool("m-ric/text-to-image", trust\_remote\_code=True)

search\_tool = DuckDuckGoSearchTool()

agent = CodeAgent(
    tools=\[search\_tool, image\_generation\_tool\],
    model=HfApiModel("Qwen/Qwen2.5-72B-Instruct"),
    planning\_interval=3 \# This is where you activate planning!
)

\# Run it!
result = agent.run(
    "How long would a cheetah at full speed take to run the length of Pont Alexandre III?",
)



---


## URL: https://huggingface.co/docs/smolagents/tutorials/inspect_runs

               

   Inspecting runs with OpenTelemetry 

smolagents documentation

Inspecting runs with OpenTelemetry


[](#inspecting-runs-with-opentelemetry)Inspecting runs with OpenTelemetry
=========================================================================



### [](#why-log-your-agent-runs)Why log your agent runs?

Agent runs are complicated to debug.

Validating that a run went properly is hard, since agent workflows are [unpredictable by design](../conceptual_guides/intro_agents) (if they were predictable, you’d just be using good old code).

And inspecting a run is hard as well: multi-step agents tend to quickly fill a console with logs, and most of the errors are just “LLM dumb” kind of errors, from which the LLM auto-corrects in the next step by writing better code or tool calls.

So using instrumentation to record agent runs is necessary in production for later inspection and monitoring!

We’ve adopted the [OpenTelemetry](https://opentelemetry.io/) standard for instrumenting agent runs.

This means that you can just run some instrumentation code, then run your agents normally, and everything gets logged into your platform.




First install the required packages. Here we install [Phoenix by Arize AI](https://github.com/Arize-ai/phoenix) because that’s a good solution to collect and inspect the logs, but there are other OpenTelemetry-compatible platforms that you could use for this collection & inspection part.

Copied

pip install smolagents
pip install arize-phoenix opentelemetry-sdk opentelemetry-exporter-otlp openinference-instrumentation-smolagents

Then run the collector in the background.

Copied

python -m phoenix.server.main serve

Finally, set up `SmolagentsInstrumentor` to trace your agents and send the traces to Phoenix at the endpoint defined below.

Copied

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from openinference.instrumentation.smolagents import SmolagentsInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace\_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

endpoint = "http://0.0.0.0:6006/v1/traces"
trace\_provider = TracerProvider()
trace\_provider.add\_span\_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint)))

SmolagentsInstrumentor().instrument(tracer\_provider=trace\_provider)

Then you can run your agents!


[](#tools)Tools
===============

![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)

![Open In Studio Lab](https://studiolab.sagemaker.aws/studiolab.svg)

Here, we’re going to see advanced tool usage.

If you’re new to building agents, make sure to first read the [intro to agents](../conceptual_guides/intro_agents) and the [guided tour of smolagents](../guided_tour).

*   [Tools](#tools)
    *   [What is a tool, and how to build one?](#what-is-a-tool-and-how-to-build-one)
    *   [Share your tool to the Hub](#share-your-tool-to-the-hub)
    *   [Import a Space as a tool](#import-a-space-as-a-tool)
    *   [Manage your agent’s toolbox](#manage-your-agents-toolbox)
    *   [Use a collection of tools](#use-a-collection-of-tools)

### [](#what-is-a-tool-and-how-to-build-one)What is a tool, and how to build one?

A tool is mostly a function that an LLM can use in an agentic system.

But to use it, the LLM will need to be given an API: name, tool description, input types and descriptions, output type.

So it cannot be only a function. It should be a class.

So at core, the tool is a class that wraps a function with metadata that helps the LLM understand how to use it.

Here’s how it looks:

Copied

from smolagents import Tool

class HFModelDownloadsTool(Tool):
    name = "model\_download\_counter"
    description = """
    This is a tool that returns the most downloaded model of a given task on the Hugging Face Hub.
    It returns the name of the checkpoint."""
    inputs = {
        "task": {
            "type": "string",
            "description": "the task category (such as text-classification, depth-estimation, etc)",
        }
    }
    output\_type = "string"

    def forward(self, task: str):
        from huggingface\_hub import list\_models

        model = next(iter(list\_models(filter\=task, sort="downloads", direction=-1)))
        return model.id

model\_downloads\_tool = HFModelDownloadsTool()

The custom tool subclasses [Tool](/docs/smolagents/v1.7.0/en/reference/tools#smolagents.Tool) to inherit useful methods. The child class also defines:

*   An attribute `name`, which corresponds to the name of the tool itself. The name usually describes what the tool does. Since the code returns the model with the most downloads for a task, let’s name it `model_download_counter`.
*   An attribute `description` is used to populate the agent’s system prompt.
*   An `inputs` attribute, which is a dictionary with keys `"type"` and `"description"`. It contains information that helps the Python interpreter make educated choices about the input.
*   An `output_type` attribute, which specifies the output type. The types for both `inputs` and `output_type` should be [Pydantic formats](https://docs.pydantic.dev/latest/concepts/json_schema/#generating-json-schema), they can be either of these: `~AUTHORIZED_TYPES()`.
*   A `forward` method which contains the inference code to be executed.

And that’s all it needs to be used in an agent!

There’s another way to build a tool. In the [guided\_tour](../guided_tour), we implemented a tool using the `@tool` decorator. The [tool()](/docs/smolagents/v1.7.0/en/reference/tools#smolagents.tool) decorator is the recommended way to define simple tools, but sometimes you need more than this: using several methods in a class for more clarity, or using additional class attributes.

In this case, you can build your tool by subclassing [Tool](/docs/smolagents/v1.7.0/en/reference/tools#smolagents.Tool) as described above.

### [](#share-your-tool-to-the-hub)Share your tool to the Hub

You can share your custom tool to the Hub by calling [push\_to\_hub()](/docs/smolagents/v1.7.0/en/reference/tools#smolagents.Tool.push_to_hub) on the tool. Make sure you’ve created a repository for it on the Hub and are using a token with read access.



model\_downloads\_tool.push\_to\_hub("{your\_username}/hf-model-downloads", token="<YOUR\_HUGGINGFACEHUB\_API\_TOKEN>")

For the push to Hub to work, your tool will need to respect some rules:

*   All methods are self-contained, e.g. use variables that come either from their args.
*   As per the above point, **all imports should be defined directly within the tool’s functions**, else you will get an error when trying to call [save()](/docs/smolagents/v1.7.0/en/reference/tools#smolagents.Tool.save) or [push\_to\_hub()](/docs/smolagents/v1.7.0/en/reference/tools#smolagents.Tool.push_to_hub) with your custom tool.
*   If you subclass the `__init__` method, you can give it no other argument than `self`. This is because arguments set during a specific tool instance’s initialization are hard to track, which prevents from sharing them properly to the hub. And anyway, the idea of making a specific class is that you can already set class attributes for anything you need to hard-code (just set `your_variable=(...)` directly under the `class YourTool(Tool):` line). And of course you can still create a class attribute anywhere in your code by assigning stuff to `self.your_variable`.

Once your tool is pushed to Hub, you can visualize it. [Here](https://huggingface.co/spaces/m-ric/hf-model-downloads) is the `model_downloads_tool` that I’ve pushed. It has a nice gradio interface.

When diving into the tool files, you can find that all the tool’s logic is under [tool.py](https://huggingface.co/spaces/m-ric/hf-model-downloads/blob/main/tool.py). That is where you can inspect a tool shared by someone else.

Then you can load the tool with [load\_tool()](/docs/smolagents/v1.7.0/en/reference/tools#smolagents.load_tool) or create it with [from\_hub()](/docs/smolagents/v1.7.0/en/reference/tools#smolagents.Tool.from_hub) and pass it to the `tools` parameter in your agent. Since running tools means running custom code, you need to make sure you trust the repository, thus we require to pass `trust_remote_code=True` to load a tool from the Hub.

Copied

from smolagents import load\_tool, CodeAgent

model\_download\_tool = load\_tool(
    "{your\_username}/hf-model-downloads",
    trust\_remote\_code=True
)

### [](#import-a-space-as-a-tool)Import a Space as a tool

You can directly import a Space from the Hub as a tool using the [Tool.from\_space()](/docs/smolagents/v1.7.0/en/reference/tools#smolagents.Tool.from_space) method!

You only need to provide the id of the Space on the Hub, its name, and a description that will help you agent understand what the tool does. Under the hood, this will use [`gradio-client`](https://pypi.org/project/gradio-client/) library to call the Space.

For instance, let’s import the [FLUX.1-dev](https://huggingface.co/black-forest-labs/FLUX.1-dev) Space from the Hub and use it to generate an image.

Copied

image\_generation\_tool = Tool.from\_space(
    "black-forest-labs/FLUX.1-schnell",
    name="image\_generator",
    description="Generate an image from a prompt"
)

image\_generation\_tool("A sunny beach")

And voilà, here’s your image! 🏖️

![](https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/transformers/sunny_beach.webp)

Then you can use this tool just like any other tool. For example, let’s improve the prompt `a rabbit wearing a space suit` and generate an image of it. This example also shows how you can pass additional arguments to the agent.

Copied

from smolagents import CodeAgent, HfApiModel

model = HfApiModel("Qwen/Qwen2.5-Coder-32B-Instruct")
agent = CodeAgent(tools=\[image\_generation\_tool\], model=model)

agent.run(
    "Improve this prompt, then generate an image of it.", additional\_args={'user\_prompt': 'A rabbit wearing a space suit'}
)

Copied

\=== Agent thoughts:
improved\_prompt could be "A bright blue space suit wearing rabbit, on the surface of the moon, under a bright orange sunset, with the Earth visible in the background"

Now that I have improved the prompt, I can use the image generator tool to generate an image based on this prompt.
>>> Agent is executing the code below:
image = image\_generator(prompt="A bright blue space suit wearing rabbit, on the surface of the moon, under a bright orange sunset, with the Earth visible in the background")
final\_answer(image)

![](https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/transformers/rabbit_spacesuit_flux.webp)

How cool is this? 🤩


### [](#manage-your-agents-toolbox)Manage your agent’s toolbox

You can manage an agent’s toolbox by adding or replacing a tool in attribute `agent.tools`, since it is a standard dictionary.

Let’s add the `model_download_tool` to an existing agent initialized with only the default toolbox.

Copied

from smolagents import HfApiModel

model = HfApiModel("Qwen/Qwen2.5-Coder-32B-Instruct")

agent = CodeAgent(tools=\[\], model=model, add\_base\_tools=True)
agent.tools\[model\_download\_tool.name\] = model\_download\_tool

Now we can leverage the new tool:

Copied

agent.run(
    "Can you give me the name of the model that has the most downloads in the 'text-to-video' task on the Hugging Face Hub but reverse the letters?"
)

Beware of not adding too many tools to an agent: this can overwhelm weaker LLM engines.

### [](#use-a-collection-of-tools)Use a collection of tools

You can leverage tool collections by using the `ToolCollection` object. It supports loading either a collection from the Hub or an MCP server tools.

#### [](#tool-collection-from-a-collection-in-the-hub)Tool Collection from a collection in the Hub

You can leverage it with the slug of the collection you want to use. Then pass them as a list to initialize your agent, and start using them!

Copied

from smolagents import ToolCollection, CodeAgent

image\_tool\_collection = ToolCollection.from\_hub(
    collection\_slug="huggingface-tools/diffusion-tools-6630bb19a942c2306a2cdb6f",
    token="<YOUR\_HUGGINGFACEHUB\_API\_TOKEN>"
)
agent = CodeAgent(tools=\[\*image\_tool\_collection.tools\], model=model, add\_base\_tools=True)

agent.run("Please draw me a picture of rivers and lakes.")

To speed up the start, tools are loaded only if called by the agent.

#### [](#tool-collection-from-any-mcp-server)Tool Collection from any MCP server

Leverage tools from the hundreds of MCP servers available on [glama.ai](https://glama.ai/mcp/servers) or [smithery.ai](https://smithery.ai/).

The MCP servers tools can be loaded in a `ToolCollection` object as follow:

Copied

from smolagents import ToolCollection, CodeAgent
from mcp import StdioServerParameters

server\_parameters = StdioServerParameters(
    command="uv",
    args=\["--quiet", "pubmedmcp@0.1.3"\],
    env={"UV\_PYTHON": "3.12", \*\*os.environ},
)

with ToolCollection.from\_mcp(server\_parameters) as tool\_collection:
    agent = CodeAgent(tools=\[\*tool\_collection.tools\], add\_base\_tools=True)
    agent.run("Please find a remedy for hangover.")

[< \> Update on GitHub](https://github.com/huggingface/smolagents/blob/main/docs/source/en/tutorials/tools.md)


[](#secure-code-execution)Secure code execution
===============================================


### [](#code-agents)Code agents

[Multiple](https://huggingface.co/papers/2402.01030) [research](https://huggingface.co/papers/2411.01747) [papers](https://huggingface.co/papers/2401.00812) have shown that having the LLM write its actions (the tool calls) in code is much better than the current standard format for tool calling, which is across the industry different shades of “writing actions as a JSON of tools names and arguments to use”.

Why is code better? Well, because we crafted our code languages specifically to be great at expressing actions performed by a computer. If JSON snippets was a better way, this package would have been written in JSON snippets and the devil would be laughing at us.

Code is just a better way to express actions on a computer. It has better:

*   **Composability:** could you nest JSON actions within each other, or define a set of JSON actions to re-use later, the same way you could just define a python function?
*   **Object management:** how do you store the output of an action like `generate_image` in JSON?
*   **Generality:** code is built to express simply anything you can do have a computer do.
*   **Representation in LLM training corpus:** why not leverage this benediction of the sky that plenty of quality actions have already been included in LLM training corpus?

This is illustrated on the figure below, taken from [Executable Code Actions Elicit Better LLM Agents](https://huggingface.co/papers/2402.01030).

![](https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/transformers/code_vs_json_actions.png)

This is why we put emphasis on proposing code agents, in this case python agents, which meant putting higher effort on building secure python interpreters.

### [](#local-python-interpreter)Local python interpreter

By default, the `CodeAgent` runs LLM-generated code in your environment. This execution is not done by the vanilla Python interpreter: we’ve re-built a more secure `LocalPythonInterpreter` from the ground up. This interpreter is designed for security by:

*   Restricting the imports to a list explicitly passed by the user
*   Capping the number of operations to prevent infinite loops and resource bloating.
*   Will not perform any operation that’s not pre-defined.

We’ve used this on many use cases, without ever observing any damage to the environment.

However this solution is not watertight: one could imagine occasions where LLMs fine-tuned for malignant actions could still hurt your environment. For instance if you’ve allowed an innocuous package like `Pillow` to process images, the LLM could generate thousands of saves of images to bloat your hard drive. It’s certainly not likely if you’ve chosen the LLM engine yourself, but it could happen.

So if you want to be extra cautious, you can use the remote code execution option described below.

### [](#e2b-code-executor)E2B code executor

For maximum security, you can use our integration with E2B to run code in a sandboxed environment. This is a remote execution service that runs your code in an isolated container, making it impossible for the code to affect your local environment.

For this, you will need to setup your E2B account and set your `E2B_API_KEY` in your environment variables. Head to [E2B’s quickstart documentation](https://e2b.dev/docs/quickstart) for more information.

Then you can install it with `pip install "smolagents[e2b]"`.

Now you’re set!

To set the code executor to E2B, simply pass the flag `use_e2b_executor=True` when initializing your `CodeAgent`. Note that you should add all the tool’s dependencies in `additional_authorized_imports`, so that the executor installs them.

Copied

from smolagents import CodeAgent, VisitWebpageTool, HfApiModel
agent = CodeAgent(
    tools = \[VisitWebpageTool()\],
    model=HfApiModel(),
    additional\_authorized\_imports=\["requests", "markdownify"\],
    use\_e2b\_executor=True
)

agent.run("What was Abraham Lincoln's preferred pet?")

E2B code execution is not compatible with multi-agents at the moment - because having an agent call in a code blob that should be executed remotely is a mess. But we’re working on adding it!

[< \> Update on GitHub](https://github.com/huggingface/smolagents/blob/main/docs/source/en/tutorials/secure_code_execution.md)

[←🛠️ Tools - in-depth guide](/docs/smolagents/tutorials/tools) [🤖 An introduction to agentic systems→](/docs/smolagents/conceptual_guides/intro_agents)
---




[](#-create-a-web-search-tool)🔍 Create a web search tool
---------------------------------------------------------

For web browsing, we can already use our pre-existing [`DuckDuckGoSearchTool`](https://github.com/huggingface/smolagents/blob/main/src/smolagents/default_tools.py#L151-L176) tool to provide a Google search equivalent.

But then we will also need to be able to peak into the page found by the `DuckDuckGoSearchTool`. To do so, we could import the library’s built-in `VisitWebpageTool`, but we will build it again to see how it’s done.

So let’s create our `VisitWebpageTool` tool from scratch using `markdownify`.

Copied

import re
import requests
from markdownify import markdownify
from requests.exceptions import RequestException
from smolagents import tool

@tool
def visit\_webpage(url: str) -> str:
    """Visits a webpage at the given URL and returns its content as a markdown string.

    Args:
        url: The URL of the webpage to visit.

    Returns:
        The content of the webpage converted to Markdown, or an error message if the request fails.
    """
    try:
        \# Send a GET request to the URL
        response = requests.get(url)
        response.raise\_for\_status()  \# Raise an exception for bad status codes

        \# Convert the HTML content to Markdown
        markdown\_content = markdownify(response.text).strip()

        \# Remove multiple line breaks
        markdown\_content = re.sub(r"\\n{3,}", "\\n\\n", markdown\_content)

        return markdown\_content

    except RequestException as e:
        return f"Error fetching the webpage: {str(e)}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"

Ok, now let’s initialize and test our tool!



print(visit\_webpage("https://en.wikipedia.org/wiki/Hugging\_Face")\[:500\])


-----------------

