import { Tweet } from "goat-x";
import fs from "fs";
import { composeContext } from "@ai16z/eliza/src/context.ts";
import { generateText, generateFormatCompletion, generateTweetActions } from "@ai16z/eliza/src/generation.ts";
import { embeddingZeroVector } from "@ai16z/eliza/src/memory.ts";
import { IAgentRuntime, ModelClass } from "@ai16z/eliza/src/types.ts";
import { stringToUuid } from "@ai16z/eliza/src/uuid.ts";
import { ClientBase } from "./base.ts";
import { settings } from "@ai16z/eliza/src/settings.ts";
import {
    postActionResponseFooter,
    parseActionResponseFromText
} from "@ai16z/eliza/src/parsing.ts";
import { messageCompletionFooter } from "@ai16z/eliza/src/parsing.ts";

const twitterPostTemplate = `{{timeline}}

{{providers}}

About {{agentName}} (@{{twitterUserName}}):
{{bio}}
{{lore}}
{{postDirections}}

{{characterPostExamples}}

# Task: Generate a post in the voice and style based on the post directions of {{agentName}}, aka @{{twitterUserName}}.
Write a single sentence post that is {{adjective}} about {{topic}} (without mentioning {{topic}} directly), from the perspective of {{agentName}}. 
Do not add commentary or ackwowledge this request, just write the post.
Your response should not contain any questions. Brief, concise statements only. No emojis. Use \\n\\n (double spaces) between statements.`;

// Template constants
export const twitterActionTemplate = 
`# INSTRUCTIONS: Analyze the following tweet and determine which actions {{agentName}} (@{{twitterUserName}}) should take.

Available actions:
[LIKE] - Tweet resonates with {{agentName}}'s interests (medium threshold)
[RETWEET] - Tweet is highly relevant to share (high threshold)
[QUOTE: <your quote text>] - Tweet needs additional context (very high threshold)
[REPLY: <your reply text>] - Tweet warrants direct response (high threshold)
[MEME: <meme concept>] - Based and banger opportunity for meme creation (very very very high threshold)

Consider:
- {{agentName}}'s personality and interests
- Content relevance and quality
- Direct mentions or relevant conversations
- Avoid short texts or repetitive engagement

Current Tweet:
{{currentTweet}}

` 
+ postActionResponseFooter;

export const twitterQuoteTweetHandlerTemplate =
    `{{relevantFacts}}
{{recentFacts}}

{{timeline}}

{{providers}}

# Task: Generate a post/reply for the character {{agentName}}.
About {{agentName}} (@{{twitterUserName}}):
{{bio}}
{{lore}}
{{topics}}

{{characterPostExamples}}

{{postDirections}}

Topics to Ignore / Not Discuss:
existential dread
void
random memecoin tickers

# Task: Generate a post/reply in the voice, style and perspective of {{agentName}} (@{{twitterUserName}}) while using the quoted tweet as additional context:
Quoted Post:
{{currentTweet}}

` + messageCompletionFooter;



// const twitterPostTemplate = settings.HYPERBOLIC_BASE_PROMPT;

export class TwitterPostClient extends ClientBase {
    onReady() {
        const generateNewTweetLoop = () => {
            this.generateNewTweet();
            this.processTweetActions();
            setTimeout(
                generateNewTweetLoop,
                (Math.floor(Math.random() * (5 - 2 + 1)) + 2) * 60 * 1000
            ); // Random interval between 4-8 hours
        };
        // setTimeout(() => {
        generateNewTweetLoop();
        // }, 5 * 60 * 1000); // Wait 5 minutes before starting the loop
    }

    constructor(runtime: IAgentRuntime) {
        // Initialize the client and pass an optional callback to be called when the client is ready
        super({
            runtime,
        });
    }

    private async generateNewTweet() {
        console.log("Generating new tweet");
        try {
            await this.runtime.ensureUserExists(
                this.runtime.agentId,
                this.runtime.getSetting("TWITTER_USERNAME"),
                this.runtime.character.name,
                "twitter"
            );

            let homeTimeline = [];

            if (!fs.existsSync("tweetcache")) fs.mkdirSync("tweetcache");
            // read the file if it exists
            if (fs.existsSync("tweetcache/home_timeline.json")) {
                homeTimeline = JSON.parse(
                    fs.readFileSync("tweetcache/home_timeline.json", "utf-8")
                );
            } else {
                homeTimeline = await this.fetchHomeTimeline(50);
                fs.writeFileSync(
                    "tweetcache/home_timeline.json",
                    JSON.stringify(homeTimeline, null, 2)
                );
            }

            const formattedHomeTimeline =
                `# ${this.runtime.character.name}'s Home Timeline\n\n` +
                homeTimeline
                    .map((tweet) => {
                        return `ID: ${tweet.id}\nFrom: ${tweet.name} (@${tweet.username})${tweet.inReplyToStatusId ? ` In reply to: ${tweet.inReplyToStatusId}` : ""}\nText: ${tweet.text}\n---\n`;
                    })
                    .join("\n");

            const state = await this.runtime.composeState(
                {
                    userId: this.runtime.agentId,
                    roomId: stringToUuid("twitter_generate_room"),
                    agentId: this.runtime.agentId,
                    content: { text: "", action: "" },
                },
                {
                    twitterUserName:
                        this.runtime.getSetting("TWITTER_USERNAME"),
                    timeline: formattedHomeTimeline,
                }
            );
            // Generate new tweet
            const context = composeContext({
                state,
                template:
                    this.runtime.character.templates?.twitterPostTemplate ||
                    twitterPostTemplate,
            });
            
            console.log(`Beginning to generate new tweet with base model`);
            const newTweetContent = await generateText({
                runtime: this.runtime,
                context,
                modelClass: ModelClass.MEDIUM,
                modelOverride: "hyperbolic"
            });

            const slice = newTweetContent.replaceAll(/\\n/g, "\n").trim();
            console.log(`New Tweet Post Content with model: ${slice}`);

            const contentLength = 240;

            let content = slice.slice(0, contentLength);
            // if its bigger than 280, delete the last line
            if (content.length > 280) {
                content = content.slice(0, content.lastIndexOf("\n"));
            }
            if (content.length > contentLength) {
                // slice at the last period
                content = content.slice(0, content.lastIndexOf("."));
            }

            // if it's still too long, get the period before the last period
            if (content.length > contentLength) {
                content = content.slice(0, content.lastIndexOf("."));
            }
            
            const formattedContent = await generateFormatCompletion(content)
            content = formattedContent
            console.log(`New Tweet Post Content after formatting: ${formattedContent}`);

            try {
                const result = await this.requestQueue.add(
                    async () => await this.twitterClient.sendTweet(content)
                );
                // read the body of the response
                const body = await result.json();
                const tweetResult = body.data.create_tweet.tweet_results.result;

                const tweet = {
                    id: tweetResult.rest_id,
                    text: tweetResult.legacy.full_text,
                    conversationId: tweetResult.legacy.conversation_id_str,
                    createdAt: tweetResult.legacy.created_at,
                    userId: tweetResult.legacy.user_id_str,
                    inReplyToStatusId:
                        tweetResult.legacy.in_reply_to_status_id_str,
                    permanentUrl: `https://twitter.com/${this.runtime.getSetting("TWITTER_USERNAME")}/status/${tweetResult.rest_id}`,
                    hashtags: [],
                    mentions: [],
                    photos: [],
                    thread: [],
                    urls: [],
                    videos: [],
                } as Tweet;

                const postId = tweet.id;
                const conversationId =
                    tweet.conversationId + "-" + this.runtime.agentId;
                const roomId = stringToUuid(conversationId);

                // make sure the agent is in the room
                await this.runtime.ensureRoomExists(roomId);
                await this.runtime.ensureParticipantInRoom(
                    this.runtime.agentId,
                    roomId
                );

                await this.cacheTweet(tweet);

                await this.runtime.messageManager.createMemory({
                    id: stringToUuid(postId + "-" + this.runtime.agentId),
                    userId: this.runtime.agentId,
                    agentId: this.runtime.agentId,
                    content: {
                        text: newTweetContent.trim(),
                        url: tweet.permanentUrl,
                        source: "twitter",
                    },
                    roomId,
                    embedding: embeddingZeroVector,
                    createdAt: tweet.timestamp * 1000,
                });

            } catch (error) {
                console.error("Error sending tweet:", error);
            }
        } catch (error) {
            console.error("Error generating new tweet:", error);
        }   

    }

    async processTweetActions() {
        try {
            console.log("Generating new advanced tweet posts");
            
            await this.runtime.ensureUserExists(
                this.runtime.agentId,
                this.runtime.getSetting("TWITTER_USERNAME"),
                this.runtime.character.name,
                "twitter"
            );
    
            let homeTimeline = [];
            homeTimeline = await this.fetchHomeTimeline(15);
            fs.writeFileSync(
                "tweetcache/home_timeline.json",
                JSON.stringify(homeTimeline, null, 2)
            );
    
            const results = [];
    
            // Process each tweet in the timeline
            for (const tweet of homeTimeline) {
                try {
                    console.log(`Processing tweet ID: ${tweet.id}`);
                    
                    const formatTweet = (tweet: any): string => {
                        return `ID: ${tweet.id}\nFrom: ${tweet.name} (@${tweet.username})${tweet.inReplyToStatusId ? ` In reply to: ${tweet.inReplyToStatusId}` : ""}\nText: ${tweet.text}\n---\n`;
                    };

                    const formattedTweet = formatTweet(tweet);

                    const tweetState = await this.runtime.composeState(
                        {
                            userId: this.runtime.agentId,
                            roomId: stringToUuid("twitter_generate_room"),
                            agentId: this.runtime.agentId,
                            content: { text: "", action: "" },
                        },
                        {
                            twitterUserName: this.runtime.getSetting("TWITTER_USERNAME"),
                            currentTweet: formattedTweet,
                        }
                    );
    
                    // Save tweet to memory first
                    // const tweetId = stringToUuid(tweet.id + "-" + this.runtime.agentId);
                    // const tweetExists = await this.runtime.messageManager.getMemoryById(tweetId);
    
                    // if (!tweetExists) {
                    //     console.log(`Tweet ${tweet.id} does not exist, saving`);
                    //     const userIdUUID = stringToUuid(tweet.userId as string);
                    //     const roomId = stringToUuid(tweet.conversationId);
                    
                    //     const message = {
                    //         id: tweetId,
                    //         agentId: this.runtime.agentId,
                    //         content: {
                    //             text: tweet.text,
                    //             url: tweet.permanentUrl,
                    //             inReplyTo: tweet.inReplyToStatusId
                    //                 ? stringToUuid(
                    //                     tweet.inReplyToStatusId +
                    //                     "-" +
                    //                     this.runtime.agentId
                    //                 )
                    //                 : undefined,
                    //         },
                    //         userId: userIdUUID,
                    //         roomId,
                    //         createdAt: tweet.timestamp * 1000,
                    //     };
                    //     await this.saveRequestMessage(message, tweetState);
                    // }
                    // else {
                    //     console.log(`Tweet ${tweet.id} exists, skipping for advanced post`);
                    // }
    
                    // Generate action decisions
                    const actionContext = composeContext({
                        state: tweetState,
                        template: this.runtime.character.templates?.twitterActionTemplate || 
                                 twitterActionTemplate,
                    });
    
                    const actionResponse = await generateTweetActions({
                        runtime: this.runtime,
                        context: actionContext,
                        modelClass: ModelClass.MEDIUM,
                        modelOverride: "hyperbolic"
                    });
    
                    if (!actionResponse) {
                        console.log(`No valid actions generated for tweet ${tweet.id}`);
                        continue;
                    }
    
                    // Execute the actions
                    const executedActions: string[] = [];
    
                    try {
                        // Like action
                        if (actionResponse.like) {
                            const likeResponse = await this.twitterClient.likeTweet(tweet.id);
                            const likeData = await likeResponse.json();
                            
                            // Check if like was successful
                            if (likeResponse.status === 200 && likeData?.data?.favorite_tweet) {
                                console.log(`Successfully liked tweet ${tweet.id}`);
                                executedActions.push('like');
                            } else {
                                console.error(`Failed to like tweet ${tweet.id}`, likeData);

                                if (likeData?.errors) {
                                    console.error('Like errors:', likeData.errors);
                                }
                            }
                        }
    
                        // Retweet action
                        if (actionResponse.retweet) {
                            try {
                                const retweetResponse = await this.twitterClient.retweet(tweet.id);
                                // Check if response is ok and parse response
                                if (retweetResponse.status === 200) {
                                    const retweetData = await retweetResponse.json();
                                    if (retweetData) { // if we got valid data back
                                        executedActions.push('retweet');
                                        console.log(`Successfully retweeted tweet ${tweet.id}`);
                                    } else {
                                        console.error(`Retweet response invalid for tweet ${tweet.id}`, retweetData);
                                    }
                                } else {
                                    console.error(`Retweet failed with status ${retweetResponse.status} for tweet ${tweet.id}`);
                                }
                            } catch (error) {
                                console.error(`Error retweeting tweet ${tweet.id}:`, error);
                                // Continue with other actions even if retweet fails
                            }
                        }
    
                        // Quote tweet action
                        if (actionResponse.quote) {
                            
                            let tweetContent = '';
                            try {
                                tweetContent = await this.generateTweetContent(tweetState);
                                console.log('Generated tweet content:', tweetContent);
                             } catch (error) {
                                console.error('Failed to generate tweet content:', error);
                             }
                
                            try {
                                const quoteResponse = await this.twitterClient.quoteTweet(tweet.id, tweetContent);
                                // Check if response is ok and parse response
                                if (quoteResponse.status === 200) {
                                    const result = await this.processTweetResponse(quoteResponse, tweetContent, 'quote');
                                    if (result.success) {
                                        executedActions.push('quote');
                                    }
                                } else {
                                    console.error(`Quote tweet failed with status ${quoteResponse.status} for tweet ${tweet.id}`);
                                }
                            } catch (error) {
                                console.error(`Error quote tweeting ${tweet.id}:`, error);
                                // Log the attempted quote text for debugging
                                console.error('Attempted quote text:', actionResponse.quote);
                                // Continue with other actions even if quote tweet fails
                            }
                        }
    
                        // Reply action
                        if (actionResponse.reply) {
                            if (actionResponse.meme) {
                                await this.handleReplyWithMeme(tweet, actionResponse, tweetState, executedActions);
                            } else {
                                await this.handleTextOnlyReply(tweet, tweetState, executedActions);

                            }
                        }
                        // Handle standalone meme
                        else if (actionResponse.meme) {
                            await this.handleStandaloneMeme(tweet, actionResponse, executedActions);

                        }
    
                        console.log(`Executed actions for tweet ${tweet.id}:`, executedActions);
                        
                        // Store the results for this tweet
                        results.push({
                            tweetId: tweet.id,
                            parsedActions: actionResponse,
                            executedActions
                        });
    
                    } catch (error) {
                        console.error(`Error executing actions for tweet ${tweet.id}:`, error);
                        continue;
                    }
    
                } catch (error) {
                    console.error(`Error processing tweet ${tweet.id}:`, error);
                    continue;
                }
            }
    
            return results;
    
        } catch (error) {
            console.error('Error in processTweetActions:', error);
            throw error;
        }
    }

    async generateAndTweetImage(prompt: string, replyToTweetId?: string) {
        try {
            // 1. Generate image
            const apiToken = this.runtime.getSetting('GLIF_API_KEY');
            const data = {
                id: "clxtc53mi0000ghv10g6irjqj",
                inputs: [prompt]
            };
    
            console.log('Generating image with prompt:', prompt);
            const genResponse = await fetch('https://simple-api.glif.app', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${apiToken}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });
    
            const result = await genResponse.json();
            if (result.error) {
                console.error(`Image generation failed: ${result.error}`);
            }
    
            if (!result.output) {
                console.error('No image URL in response');
            }
    
            // 2. Download the generated image
            console.log('Downloading generated image from:', result.output);
            const imageUrl = result.output.replace(/[<>]/g, ''); // Remove <> if present
            const imageResponse = await fetch(imageUrl);
            const imageBuffer = Buffer.from(await imageResponse.arrayBuffer());
    
            // 3. Upload media to Twitter
            console.log('Uploading media to Twitter');
            const mediaUploadResponse = await this.twitterClient.uploadMedia(imageBuffer, 'image/jpeg');
            
            if (!mediaUploadResponse.media_id_string) {
                console.error('No media ID returned from upload');
            }
    
            // 4. Create tweet with media only (no text)
            console.log('Creating tweet with media only');
            const tweetResponse = await this.twitterClient.sendTweet(
                '',  // Empty string for text
                replyToTweetId,
                [mediaUploadResponse.media_id_string]
            );
    
            const tweetResult = await tweetResponse.json();
            if (tweetResponse.status === 200) {
                console.log('Successfully tweeted with image');
                return {
                    success: true,
                    mediaId: mediaUploadResponse.media_id_string,
                    tweet: tweetResult
                };
            } else {
                console.error('Tweet creation failed');
            }
    
        } catch (error) {
            console.error('Error in generateAndTweetImage:', error);
        }
    }
    
    async generateTweetContent(
        this: any,  // to access the class properties
        tweetState: any
     ): Promise<string> {
        try {
            const context = composeContext({
                state: tweetState,
                template: this.runtime.character.templates?.twitterActionTemplate || 
                         this.twitterPostTemplate,
            });
            
            console.log(`Beginning to generate new tweet with base model`);
            const newTweetContent = await generateText({
                runtime: this.runtime,
                context,
                modelClass: ModelClass.MEDIUM,
                modelOverride: "hyperbolic"
            });
     
            const slice = newTweetContent.replaceAll(/\\n/g, "\n").trim();
            console.log(`New Tweet Post Content with model: ${slice}`);
     
            const contentLength = 240;
     
            let content = slice.slice(0, contentLength);
            
            // if its bigger than 280, delete the last line
            if (content.length > 280) {
                content = content.slice(0, content.lastIndexOf("\n"));
            }
            
            // Slice at the last period if still too long
            if (content.length > contentLength) {
                content = content.slice(0, content.lastIndexOf("."));
            }
     
            // if it's still too long, get the period before the last period
            if (content.length > contentLength) {
                content = content.slice(0, content.lastIndexOf("."));
            }
            
            const formattedContent = await this.generateFormatCompletion(content);
            console.log(`New Tweet Post Content after formatting: ${formattedContent}`);
     
            return formattedContent;
     
        } catch (error) {
            console.error('Error generating tweet content:', error);
            throw error;
        }
     }

     async processTweetResponse(
        response: Response,
        tweetContent: string,
        actionType: 'quote' | 'reply' | 'meme'
    ) {
        try {
            const body = await response.json();
            const tweetResult = body.data.create_tweet.tweet_results.result;
    
            const newTweet = {
                id: tweetResult.rest_id,
                text: tweetResult.legacy.full_text,
                conversationId: tweetResult.legacy.conversation_id_str,
                createdAt: tweetResult.legacy.created_at,
                userId: tweetResult.legacy.user_id_str,
                inReplyToStatusId: tweetResult.legacy.in_reply_to_status_id_str,
                permanentUrl: `https://twitter.com/${this.runtime.getSetting("TWITTER_USERNAME")}/status/${tweetResult.rest_id}`,
                hashtags: [],
                mentions: [],
                photos: [],
                thread: [],
                urls: [],
                videos: [],
            } as Tweet;
    
            const postId = newTweet.id;
            const conversationId = newTweet.conversationId + "-" + this.runtime.agentId;
            const roomId = stringToUuid(conversationId);
    
            // make sure the agent is in the room
            await this.runtime.ensureRoomExists(roomId);
            await this.runtime.ensureParticipantInRoom(
                this.runtime.agentId,
                roomId
            );
    
            await this.cacheTweet(newTweet);
    
            await this.runtime.messageManager.createMemory({
                id: stringToUuid(postId + "-" + this.runtime.agentId),
                userId: this.runtime.agentId,
                agentId: this.runtime.agentId,
                content: {
                    text: tweetContent.trim(),
                    url: newTweet.permanentUrl,
                    source: "twitter",
                },
                roomId,
                embedding: embeddingZeroVector,
                createdAt: newTweet.timestamp * 1000,
            });
    
            return {
                success: true,
                tweet: newTweet,
                actionType
            };
        } catch (error) {
            console.error(`Error processing ${actionType} tweet response:`, error);
            return {
                success: false,
                error,
                actionType
            };
        }
    }

    private async handleReplyWithMeme(tweet: any, actionResponse: any, tweetState: any, executedActions: string[]) {
        try {
            const result = await this.generateAndTweetImage(
                actionResponse.meme,
                tweet.id
            );
            if (result?.success) {
                executedActions.push('meme');
            }
        } catch (error) {
            console.error('Failed to generate and tweet meme:', error);
            // Fallback to text-only reply
            await this.handleTextOnlyReply(tweet, tweetState, executedActions);
        }
    }
    
    private async handleTextOnlyReply(tweet: any, tweetState: any, executedActions: string[]) {
        try {
            const tweetContent = await this.generateTweetContent(tweetState);
            console.log('Generated tweet content:', tweetContent);
            
            const tweetResponse = await this.twitterClient.sendTweet(
                tweetContent,
                tweet.id
            );
            if (tweetResponse.status === 200) {
                console.log('Successfully tweeted with reply');
                executedActions.push('reply');
            } else {
                console.error('Tweet creation failed (reply)');
            }
        } catch (error) {
            console.error('Failed to generate tweet content:', error);
        }
    }
    
    private async handleStandaloneMeme(tweet: any, actionResponse: any, executedActions: string[]) {
        try {
            const result = await this.generateAndTweetImage(
                actionResponse.meme,
                tweet.id
            );
            if (result?.success) {
                executedActions.push('meme');
            }
        } catch (error) {
            console.error('Failed to generate and tweet standalone meme:', error);
        }
    }
    
}
