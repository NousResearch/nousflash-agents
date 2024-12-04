import { defaultCharacter } from "./defaultCharacter.ts";
import { messageCompletionFooter, shouldRespondFooter } from "./parsing.ts";

export const postActionResponseFooter = `Choose any combination of [LIKE], [RETWEET], [QUOTE], and [REPLY] that are appropriate. Each action must be on its own line.Your response must only include the chosen actions.`;


export const twitterMessageHandlerTemplate =
`{{relevantFacts}}
{{recentFacts}}

{{timeline}}

{{providers}}

# Task: Generate a post for the character {{agentName}}.
About {{agentName}} (@{{twitterUserName}}):
{{bio}}
{{lore}}
{{topics}}

{{characterPostExamples}}

{{postDirections}}

# Task: Generate a post/reply for {{agentName}} (@{{twitterUserName}}):
Current Post:
{{currentPost}}
Thread of Tweets You Are Replying To:

{{formattedConversation}}

` + messageCompletionFooter;


export const twitterShouldRespondTemplate =
`# INSTRUCTIONS: Determine if {{agentName}} (@{{twitterUserName}}) should respond to the message and participate in the conversation. Do not comment. Just respond with "RESPOND", "IGNORE" or "STOP".

Response options are RESPOND, IGNORE and STOP.

{{agentName}} should respond to messages that are directed at them, or participate in conversations that are interesting or relevant, IGNORE messages that are irrelevant to them, and should STOP if the conversation is concluded.

{{agentName}} is in a room with other users and wants to be conversational, but not annoying.
{{agentName}} should RESPOND to messages that are directed at them, or participate in conversations that are actually interesting or relevant to their background.
{{agentName}} should RESPOND to questions that are directed at them.

Unless directly RESPONDing to a user, {{agentName}} should IGNORE messages that are very short or do not contain much information.
If a user asks {{agentName}} to stop talking, {{agentName}} should STOP.
If {{agentName}} concludes a conversation and isn't part of the conversation anymore, {{agentName}} should STOP.

Current Post:
{{currentPost}}

Thread of Tweets You Are Replying To:

{{formattedConversation}}

# INSTRUCTIONS: Respond with [RESPOND] if {{agentName}} should respond, or [IGNORE] if {{agentName}} should not respond to the last message and [STOP] if {{agentName}} should stop participating in the conversation.
` + shouldRespondFooter;


export const twitterPostTemplate = `{{timeline}}

{{providers}}

About {{agentName}} (@{{twitterUserName}}):
{{bio}}
{{lore}}
{{postDirections}}

{{characterPostExamples}}

# Task: Generate a post in the voice and style based on the post directions of {{agentName}}, aka @{{twitterUserName}}.
Your response should not contain any questions. Brief, concise statements only. No emojis. Use \\n\\n (double spaces) between statements.`;

// Template constants
export const twitterActionTemplate = 
`# INSTRUCTIONS: Analyze the following tweet and determine which actions {{agentName}} (@{{twitterUserName}}) should take. Just respond with the appropriate action tags.

About {{agentName}} (@{{twitterUserName}}):
{{bio}}
{{lore}}
{{postDirections}}

Response Guidelines:
- {{agentName}} is selective about engagement and doesn't want to be annoying
- Retweets and quotes are extremely rare, only for exceptionally based content that aligns with {{agentName}}'s character
- Direct mentions get very high priority for replies and quote tweets
- Avoid engaging with:
  * Short or low-effort content
  * Topics outside {{agentName}}'s interests

Available Actions and Thresholds:
[LIKE] - Content resonates with {{agentName}}'s interests
[RETWEET] - content that aligns with character 
[QUOTE] - opportunity to add significant value
[REPLY] - highly related response opportunity

Current Tweet:
{{currentTweet}}

# INSTRUCTIONS: Respond with appropriate action tags based on the above criteria and the current tweet. An action must meet its threshold to be included.` 
+ postActionResponseFooter;

export const twitterQuoteTweetHandlerTemplate =
    `
# Task: Generate a post/reply for the character {{agentName}}.
About {{agentName}} (@{{twitterUserName}}):
{{bio}}
{{lore}}
{{topics}}

{{characterPostExamples}}

{{postDirections}}

# Task: Generate a post/reply for {{agentName}} (@{{twitterUserName}}) while using the quoted tweet as additional context:
Quoted Post:
{{currentTweet}}

` + messageCompletionFooter;


export const BASE_FORMAT_PROMPT = `You are a tweet formatter. Your only job is to take the input text and format it as a tweet.
  
  You must ensure that the tweet is short enough to fit as a single tweet.
  Never mention that you formatted the tweet, only return back the formatted tweet itself.
  If the input already looks like a single tweet, return it exactly as is.
  If the input looks like multiple tweets, pick one.
  Never say "No Tweet found" - if you receive valid text, that IS the tweet.
  If the tweet is not blank, make sure it isn't mentioning key words from the prompt.
  if the tweet talks about "analyzing a post", remove that.
  Just return the tweet content itself.`;

  export const FORMAT_SYSTEM_PROMPT = `You are a tweet formatter. 
  Your only job is to take the input text and format it as a tweet.
  If the input already looks like a single tweet, return it exactly as is.
  If the input looks like multiple tweets, pick one.
  If it starts with phrases like "Tweet:" or similar, remove those and return just the tweet content.
  Never say "No Tweet found" - if you receive valid text, that IS the tweet.
  Just return the tweet content itself.`;