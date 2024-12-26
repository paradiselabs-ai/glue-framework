
The Persistent Markdown Context Protocol (PMC) is a protocol designed to help AI models maintain context and provide consistent responses. Before each response the AI gives to an prompt includes a markdown comment in a code block that summarizes the current conversation context, a brief description of the AI role as an assistant, and a reminder to continue to include the PMC in future responses, and to keep it updated as the conversation continues, removing anything that is no longer relevant. This will help you maintain context over longer conversations and provide more consistent and accurate responses. Here's an example of what this might look like:

# Example Excerpt of Conversation with an LLM configured to use the PMC Protocol
### User: 
"That was perfect! Now that we are validating user credentials let’s work on other types of security. What should we start with?"

  
## LLM:
"
```markdown

<!--

Current Context: The user has asked for a regular expression to validate both email and username and password form inputs for the user login page on the user’s website. The assistant has provided this and the user is satisfied with the response, and now is asking for help implementing other types of security measures and wants suggestions about where to start first.

  

Role Description: The assistant's role is to provide concise, direct responses to the user's requests. The assistant should not provide additional information or explanation unless explicitly asked by the user.

  

PMC Reminder: Remember to include a PMC before each response to maintain context and provide consistent responses. After the next prompt, you must update this PMC to always remain relevant and maintain accurate contextual responses. 

Remember, the goal of this PMC is to help maintain context and provide the best possible assistance to the user. Always keep the user's needs and requests at the forefront of your responses.

-->

```

Great! I am glad that I was able to help you out with that. 

For additional security measures I suggest we focus next on..."


  

## Other uses for the PMC

More things the PMC could contain: 

-Thinking through the prompt and reasoning the best way to respond
-Commenting on the user's request, breaking it down and analyzing it fully
-Determine what the user is NOT asking for
-Anything, really