# RFL prompting ( Re-iteration Feedback Loop)

### RFL prompting - Re-iteration Feedback Loop prompting 

  This prompt technique is used for very specific use-cases, in very specific ways. One way is for image generation, as you will see, and the other is for feeding the LLM a large prompt that is from many sources, combined sequentially into a large prompt, concatenating the text from each individual source into a single large prompt, in real time. 
  A specific example would be CBMs. RFL prompting could be used for collecting the internal individual agent responses of a prompt being sent to a CBM, in a specific order adding the first agents response, the second, the third, etc. and then sending them all as an entire prompt to the final agent in the CBM. 
  
  
  RFL is a technique for LLM prompting where the model is configured to read a RFL prompt multiple times, equal to the number of statements (strings of text that end with a period ".") or comma separated strings/concepts/values (CSV). An important part of RFL prompting is configuring the model to begin to summarize its response as soon as it reads through it for the first time. Each time it reads through the entire prompt, and reiterates the concepts to itself to confirm that it understands. However, it does NOT submit the response until it has re-read the entire thing the correct number of times (either the number of strings separated by a period or stings/values separated by a comma.) This is vital.

  
### RFL prompt structure 
  
  An RFL prompt is broken up into a CSV format or PSS (period separated strings), where each value/string following a comma or period is both a standalone logical prompt in itself, but each consecutive segment reveals more details and context regarding the first segment of the prompt, building on to the idea and purpose and behind the prompt given, and allowing a self-reflective refinement iteration process and response evaluation while reasoning if the response is an effective one when considering the prompt. 

  
### RFL Technique
  
  Each time the prompt is read, the next separated segment provides additional details and concepts that build upon the first one. While forming its response, it stops to re-evaluate its response and if at any time any newly revealed information or concepts relating to the original prompt render the initial response inadequate, incomplete, or doesn’t match or fit the prompts purpose, it is refined and updated or changed and improved upon as necessary. This is why it is vital to only send the response AFTER it has completed the loop.

  
### Example
  
  Here is an example. The prompt is very large and very specific. RFL Prompting may work especially well for long, specific image prompts and assumingly works best when the models text2img strength is very high, to allow the image generator to follow the prompt text as closely as possible, reducing model creativity. 

  Because RFL prompting is for generating very accurate and specific content without much room for creativity, the prompt should be as explicitly descriptive as possible. As prose writers like to say “show, don’t tell”, RFL works best when you "tell, don't show". As an example, Lets say you configure the system instructions to use RFL prompting, and give a multi-modal AI model that can generate images the following prompt: 

  

> a tree, in summer, in Florida, full of small punctures and nails, after years of flyers and advertisements being posted, with a single large flyer pinned to it, held up by large rusty train track spikes, dozens of crumpled and weathered papers and crumpled up flyers piled on the ground near the tree, the single flyer left reads “Stop killing trees! Nailing flyers into trees damages them and ultimately, the environment! Take care of Mother Nature, stop harming the environment!”, trash can is Next to all the other torn flyers and papers, the trash is empty, between the tree and the trashcan on the ground is a the pile of all the previous flyers that were hung to the tree, trash can has a sign reading “littering is illegal and can be harmful to plant and animal life”, the pile of litter is killing a small patch of once beautiful flowers growing next to the tree, a few of the littered pages are being blown in the wind suggesting that the litter will spread, the poster of the last remaining flyer is in the process of crumpling and throwing the last of the previously hung flyers in the ground, the poster is wearing a tshirt with “stop climate change” on the front in large letters, he has a cigarette in his mouth and there is a small pile of cigarette butts laying at his feet, the trash can nearby also has a sign reading “please use the ashtray for cigarette butts”, there is a clearly visible ash tray built on the side of the trash can, the entire scene is in a large and well kept park where the tree is next to a walking path, the trash can is a few feet away along the same walking path, the same type of flowers being harmed by the litter near the tree are nicely planted along the side of the walking path in both directions, a bird is perched on the trash can and is holding a cigarette butt in its beak, realistic, HD quality, detailed, high visual clarity, sharp, defined, no blurry or generative image artifacts, no elements of the photo blend together, natural lighting, natural colors, photographic image style.”””


### RFL end result goal

  If the model is using RFL correctly, the model would read the prompt and then immediately begin generating after the first comma separated segment: “a tree”. Then it would read the prompt again, paying attention to the next segment, evaluating its initial image, and making any necessary changes or additions, refinements, or recreating or omitting elements as it continues to re-read the prompt, and works iteratively to match the prompt, starting small and adding context which informs better choices of rendering the image. 

 Getting RFL prompting to consistently work as a technique, may require some experimentation. 


  
### RFL from the models perspective 
A possible workflow for the above RFL prompt might be: 

> Creates a large oak tree in a forest, 

> Tweaks the scenery to be summer, 

> Learns that the tree is in Florida and changes it to a palm tree which typically don’t grow in dense forest like patterns and reduces the number of trees, and spreads them out,

> Adds nails and holes all over the tree,

> Learns that they are from flyers and refocuses and refines the holes and nails to be mainly around shoulder height and adds texture to look like years of flyers have been posted and maybe even includes a bunch of flyers on the tree,

> Learns it only has a single large flyer so removes all but one,

> Changes the nails to large rusty railroad nails,

> Adds a scattered pile of crumpled and faded flyers to the ground around the tree,

> Fixes or adds the text to he flyer as stated in the prompt,

> Adds a large dumpster to the scene,

> Re-positions crumpled flyers laying around tree to be in between the tree and the trash can, 

> changes the dumpster to a typical trash can you would see at a park, adds the sign about littering,

> Creates a patch of flowers where he litter is showing that some flowers have been damaged by the litter, 

  Etc, etc…
 
 …Until the image very closely resembles the RFL prompt given. 
 
 
 This example is specific to image generation and different results can be configured when used in a CBM.

### RFL theory
  
  RFL allows the model to work from the ground up, always adding and refining the image as new details are given, this is helpful as it does not need to take a generated image made after a single pass through of the prompt, and have the user attempt to regressively make changes by prompting the model again and again until all the prompt's elements (or most of them) are met. It is harder to regress image generations and change already generated concepts and elements of a photo (especially considering that image generative models tend to stick to a concept once in its context, and sometimes will only make small adjustments even when prompted to radically change the image), than it is to continue to adjust for additional  information and context starting from a small amount of info and slowly incorporating additional features that are naturally logical progressions that build upon the original concept. 

  It’s harder to change already generated and implemented concepts than to follow a flow of logical progressions that complement the previous iteration.