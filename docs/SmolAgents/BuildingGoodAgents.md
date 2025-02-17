## URL: https://huggingface.co/docs/smolagents/en/tutorials/building_good_agents

               

   Building good agents 

smolagents documentation

Building good agents

smolagents
==========

🏡 View all docsAWS Trainium & InferentiaAccelerateAmazon SageMakerArgillaAutoTrainBitsandbytesChat UICompetitionsDataset viewerDatasetsDiffusersDistilabelEvaluateGradioHubHub Python LibraryHugging Face Generative AI Services (HUGS)Huggingface.jsInference API (serverless)Inference Endpoints (dedicated)LeaderboardsLightevalOptimumPEFTSafetensorsSentence TransformersTRLTasksText Embeddings InferenceText Generation InferenceTokenizersTransformersTransformers.jssmolagentstimm

Search documentation

⌘K

mainv1.7.0v1.6.0v1.5.1v1.4.1v1.3.0v1.2.2v1.1.0v0.1.3 EN

[7,195](https://github.com/huggingface/smolagents)

![Hugging Face's logo](/front/assets/huggingface_logo-noborder.svg)

Join the Hugging Face community

and get access to the augmented documentation experience

Collaborate on models, datasets and Spaces

Faster examples with accelerated inference

Switch between documentation themes

[Sign Up](/join)

to get started

[](#building-good-agents)Building good agents
=============================================

![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)

![Open In Studio Lab](https://studiolab.sagemaker.aws/studiolab.svg)

There’s a world of difference between building an agent that works and one that doesn’t. How can we build agents that fall into the latter category? In this guide, we’re going to talk about best practices for building agents.

If you’re new to building agents, make sure to first read the [intro to agents](../conceptual_guides/intro_agents) and the [guided tour of smolagents](../guided_tour).

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

[< \> Update on GitHub](https://github.com/huggingface/smolagents/blob/main/docs/source/en/tutorials/building_good_agents.md)

[←Guided tour](/docs/smolagents/en/guided_tour) [📊 Inspect your agent runs using telemetry→](/docs/smolagents/en/tutorials/inspect_runs)
---


## URL: https://huggingface.co/docs/smolagents/en/tutorials/inspect_runs

               

   Inspecting runs with OpenTelemetry 

smolagents documentation

Inspecting runs with OpenTelemetry

smolagents
==========

🏡 View all docsAWS Trainium & InferentiaAccelerateAmazon SageMakerArgillaAutoTrainBitsandbytesChat UICompetitionsDataset viewerDatasetsDiffusersDistilabelEvaluateGradioHubHub Python LibraryHugging Face Generative AI Services (HUGS)Huggingface.jsInference API (serverless)Inference Endpoints (dedicated)LeaderboardsLightevalOptimumPEFTSafetensorsSentence TransformersTRLTasksText Embeddings InferenceText Generation InferenceTokenizersTransformersTransformers.jssmolagentstimm

Search documentation

⌘K

mainv1.7.0v1.6.0v1.5.1v1.4.1v1.3.0v1.2.2v1.1.0v0.1.3 EN

[7,195](https://github.com/huggingface/smolagents)

![Hugging Face's logo](/front/assets/huggingface_logo-noborder.svg)

Join the Hugging Face community

and get access to the augmented documentation experience

Collaborate on models, datasets and Spaces

Faster examples with accelerated inference

Switch between documentation themes

[Sign Up](/join)

to get started

[](#inspecting-runs-with-opentelemetry)Inspecting runs with OpenTelemetry
=========================================================================

![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)

![Open In Studio Lab](https://studiolab.sagemaker.aws/studiolab.svg)

If you’re new to building agents, make sure to first read the [intro to agents](../conceptual_guides/intro_agents) and the [guided tour of smolagents](../guided_tour).

### [](#why-log-your-agent-runs)Why log your agent runs?

Agent runs are complicated to debug.

Validating that a run went properly is hard, since agent workflows are [unpredictable by design](../conceptual_guides/intro_agents) (if they were predictable, you’d just be using good old code).

And inspecting a run is hard as well: multi-step agents tend to quickly fill a console with logs, and most of the errors are just “LLM dumb” kind of errors, from which the LLM auto-corrects in the next step by writing better code or tool calls.

So using instrumentation to record agent runs is necessary in production for later inspection and monitoring!

We’ve adopted the [OpenTelemetry](https://opentelemetry.io/) standard for instrumenting agent runs.

This means that you can just run some instrumentation code, then run your agents normally, and everything gets logged into your platform.

Here’s how it then looks like on the platform:

![](https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/smolagents/inspect_run_phoenix.gif)

### [](#setting-up-telemetry-with-arize-ai-phoenix)Setting up telemetry with Arize AI Phoenix

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

Copied

from smolagents import (
    CodeAgent,
    ToolCallingAgent,
    ManagedAgent,
    DuckDuckGoSearchTool,
    VisitWebpageTool,
    HfApiModel,
)

model = HfApiModel()

agent = ToolCallingAgent(
    tools=\[DuckDuckGoSearchTool(), VisitWebpageTool()\],
    model=model,
)
managed\_agent = ManagedAgent(
    agent=agent,
    name="managed\_agent",
    description="This is an agent that can do web search.",
)
manager\_agent = CodeAgent(
    tools=\[\],
    model=model,
    managed\_agents=\[managed\_agent\],
)
manager\_agent.run(
    "If the US keeps its 2024 growth rate, how many years will it take for the GDP to double?"
)

Voilà! You can then navigate to `http://0.0.0.0:6006/projects/` to inspect your run!

![](https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/smolagents/inspect_run_phoenix.png)

You can see that the CodeAgent called its managed ToolCallingAgent (by the way, the managed agent could be have been a CodeAgent as well) to ask it to run the web search for the U.S. 2024 growth rate. Then the managed agent returned its report and the manager agent acted upon it to calculate the economy doubling time! Sweet, isn’t it?

[< \> Update on GitHub](https://github.com/huggingface/smolagents/blob/main/docs/source/en/tutorials/inspect_runs.md)

[←✨ Building good agents](/docs/smolagents/en/tutorials/building_good_agents)