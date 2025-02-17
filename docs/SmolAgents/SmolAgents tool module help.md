Help on class Tool in module smolagents.tools:

class Tool(builtins.object)
 |  Tool(*args, **kwargs)
 |
 |  A base class for the functions used by the agent. Subclass this and implement the `forward` method as well as the
 |  following class attributes:
 |
 |  - **description** (`str`) -- A short description of what your tool does, the inputs it expects and the output(s) it
 |    will return. For instance 'This is a tool that downloads a file from a `url`. It takes the `url` as input, and
 |    returns the text contained in the file'.
 |  - **name** (`str`) -- A performative name that will be used for your tool in the prompt to the agent. For instance
 |    `"text-classifier"` or `"image_generator"`.
 |  - **inputs** (`Dict[str, Dict[str, Union[str, type]]]`) -- The dict of modalities expected for the inputs.
 |    It has one `type`key and a `description`key.
 |    This is used by `launch_gradio_demo` or to make a nice space from your tool, and also can be used in the generated
 |    description for your tool.
 |  - **output_type** (`type`) -- The type of the tool output. This is used by `launch_gradio_demo`
 |    or to make a nice space from your tool, and also can be used in the generated description for your tool.
 |
 |  You can also override the method [`~Tool.setup`] if your tool has an expensive operation to perform before being
 |  usable (such as loading a model). [`~Tool.setup`] will be called the first time you use your tool, but not at
 |  instantiation.
 |
 |  Methods defined here:
 |
 |  __call__(self, *args, sanitize_inputs_outputs: bool = False, **kwargs)
 |      Call self as a function.
 |
 |  __init__(self, *args, **kwargs)
 |      Initialize self.  See help(type(self)) for accurate signature.
 |
 |  forward(self, *args, **kwargs)
 |
 |  push_to_hub(self, repo_id: str, commit_message: str = 'Upload tool', private: Optional[bool] = None, token: Union[bool, str, NoneType] = None, crea
te_pr: bool = False) -> str
 |      Upload the tool to the Hub.
 |
 |      For this method to work properly, your tool must have been defined in a separate module (not `__main__`).
 |      For instance:
 |      ```
 |      from my_tool_module import MyTool
 |      my_tool = MyTool()
 |      my_tool.push_to_hub("my-username/my-space")
 |      ```
 |
 |      Parameters:
 |          repo_id (`str`):
 |              The name of the repository you want to push your tool to. It should contain your organization name when
 |              pushing to a given organization.
 |          commit_message (`str`, *optional*, defaults to `"Upload tool"`):
 |              Message to commit while pushing.
 |          private (`bool`, *optional*):
 |              Whether to make the repo private. If `None` (default), the repo will be public unless the organization's default is private. This value
 is ignored if the repo already exists.
 |          token (`bool` or `str`, *optional*):
 |              The token to use as HTTP bearer authorization for remote files. If unset, will use the token generated
 |              when running `huggingface-cli login` (stored in `~/.huggingface`).
 |          create_pr (`bool`, *optional*, defaults to `False`):
 |              Whether or not to create a PR with the uploaded files or directly commit.
 |
: