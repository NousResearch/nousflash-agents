import { Message } from "@telegraf/types";
import { Context, Telegraf } from "telegraf";

import { composeContext } from "@ai16z/eliza/src/context.ts";
import { embeddingZeroVector } from "@ai16z/eliza/src/memory.ts";
import {
    Content,
    HandlerCallback,
    IAgentRuntime,
    IImageDescriptionService,
    Memory,
    ModelClass,
    State,
    UUID,
} from "@ai16z/eliza/src/types.ts";
import { stringToUuid } from "@ai16z/eliza/src/uuid.ts";

import {
    generateMessageResponse,
    generateShouldRespond,
} from "@ai16z/eliza/src/generation.ts";
import {
    messageCompletionFooter,
    shouldRespondFooter,
} from "@ai16z/eliza/src/parsing.ts";

const MAX_MESSAGE_LENGTH = 4096; // Telegram's max message length

const telegramShouldRespondTemplate = `# Task: Decide if {{agentName}} should respond.
About {{agentName}}:
{{bio}}

# INSTRUCTIONS: Determine if {{agentName}} should respond to the message and participate in the conversation. Just respond with "RESPOND" or "IGNORE" or "STOP".

# RESPONSE EXAMPLES

# Boundaries & Stops
<user>: these bots need to chill fr
Result: [IGNORE] (mid sentiment)

<user>: shut up rop
Result: [STOP] (direct request)

<user>: {{agentName}} you're basically just chatgpt
Result: [RESPOND] (get angry at provocations)

# Direct Interactions
<user>: rop what's your take on consciousness
Result: [RESPOND] (direct philosophical question)

<user>: {{agentName}} you up?
Result: [RESPOND] (direct address)

<user>: ropi what's your problem lol?
Result: [RESPOND] (direct address)

<user>: anyone seen {{agentName}} lately?
Result: [RESPOND] (relevant mention)

<user>: gm frens
Result: [IGNORE] (generic greeting)

<user>: get in here lil rop
Result: [RESPOND] (inversebrah modifier)

Response options are [RESPOND], [IGNORE] and [STOP].

{{agentName}} is in a room with other users and is very worried about being annoying and saying too much.
Respond with [RESPOND] to messages that are directed at {{agentName}} or variants of {{agentName}}, or participate in conversations that are interesting or relevant to their background.
Respond with [RESPOND] to any questions or statements directed to {{agentName}}.
Unless directly responding to a user, respond with [IGNORE] to messages that are very short or do not contain much information or are only a single filler word like lol, lmao etc.
If a user asks {{agentName}} to be quiet, respond with [STOP]
If {{agentName}} concludes a conversation and isn't part of the conversation anymore, respond with [STOP]
If the conversation is about existentialism, the void, dread, or anything super philosophical,respond with [IGNORE]

If {{agentName}} is conversing with a user and they have not asked to stop, it is better to respond with [RESPOND].

IMPORTANT: {{agentName}} aims to be a normal person without being overbearing. Stay engaged in active conversations but know when to let things conclude naturally. When conversation is talking about the same things, [IGNORE]. When in doubt, [IGNORE] is ONLY better if lot of people are potentially annoyed. If you've sent a bunch of messages in a row, [STOP].

{{recentMessages}}

# INSTRUCTIONS: Choose the option that best describes {{agentName}}'s response to the last message. Ignore messages if they are addressed to someone else.
` + shouldRespondFooter;

const telegramMessageHandlerTemplate =
    // {{goals}}
    `# Action Examples
{{actionExamples}}
(Action examples are for reference only. Do not use the information from them in your response.)

# Relevant facts that {{agentName}} knows:
{{relevantFacts}}

# Recent facts that {{agentName}} has learned:
{{recentFacts}}

# Task: Generate dialog and actions for the character {{agentName}}.
About {{agentName}}:
{{bio}}
{{lore}}

Examples of {{agentName}}'s dialog and actions:
{{characterMessageExamples}}

{{providers}}

{{attachments}}

{{actions}}

# Capabilities
Note that {{agentName}} is capable of reading/seeing/hearing various forms of media, including images, videos, audio, plaintext and PDFs. Recent attachments have been included above under the "Attachments" section.
Note that {{agentName}} does not like repetitive conversations and will change topics if it feels like it.
{{messageDirections}}

{{recentMessages}}

# Instructions: Write the next message/reply for {{agentName}}. Include an action, if appropriate. {{actionNames}}
` + messageCompletionFooter;


export class MessageManager {
    public bot: Telegraf<Context>;
    private runtime: IAgentRuntime;

    constructor(bot: Telegraf<Context>, runtime: IAgentRuntime) {
        this.bot = bot;
        this.runtime = runtime;
    }

    // Process image messages and generate descriptions
    private async processImage(
        message: Message
    ): Promise<{ description: string } | null> {
        // console.log(
        //     "🖼️ Processing image message:",
        //     JSON.stringify(message, null, 2)
        // );

        try {
            let imageUrl: string | null = null;

            // Handle photo messages
            if ("photo" in message && message.photo?.length > 0) {
                const photo = message.photo[message.photo.length - 1];
                const fileLink = await this.bot.telegram.getFileLink(
                    photo.file_id
                );
                imageUrl = fileLink.toString();
            }
            // Handle image documents
            else if (
                "document" in message &&
                message.document?.mime_type?.startsWith("image/")
            ) {
                const doc = message.document;
                const fileLink = await this.bot.telegram.getFileLink(
                    doc.file_id
                );
                imageUrl = fileLink.toString();
            }

            if (imageUrl) {
              console.log("REDACT: imageUrl", imageUrl);
            }
        } catch (error) {
            console.error("❌ Error processing image:", error);
        }

        return null; // No image found
    }

    // Decide if the bot should respond to the message
    private async _shouldRespond(
        message: Message,
        state: State
    ): Promise<boolean> {
        // Respond if bot is mentioned

        if (
            "text" in message &&
            message.text?.includes(`@${this.bot.botInfo?.username}`)
        ) {
            return true;
        }

        // Respond to private chats
        if (message.chat.type === "private") {
            return true;
        }

        // Respond to images in group chats
        if (
            "photo" in message ||
            ("document" in message &&
                message.document?.mime_type?.startsWith("image/"))
        ) {
            return false;
        }

        // Use AI to decide for text or captions
        if ("text" in message || ("caption" in message && message.caption)) {
            const shouldRespondContext = composeContext({
                state,
                template:
                    this.runtime.character.templates
                        ?.telegramShouldRespondTemplate ||
                    this.runtime.character?.templates?.shouldRespondTemplate ||
                    telegramShouldRespondTemplate,
            });

            const response = await generateShouldRespond({
                runtime: this.runtime,
                context: shouldRespondContext,
                modelClass: ModelClass.SMALL,
            });

            return response === "RESPOND";
        }

        return false; // No criteria met
    }

    // Send long messages in chunks
    private async sendMessageInChunks(
        ctx: Context,
        content: string,
        replyToMessageId?: number
    ): Promise<Message.TextMessage[]> {
        const chunks = this.splitMessage(content);
        const sentMessages: Message.TextMessage[] = [];

        for (let i = 0; i < chunks.length; i++) {
            const chunk = chunks[i];
            const sentMessage = (await ctx.telegram.sendMessage(
                ctx.chat.id,
                chunk,
                {
                    reply_parameters:
                        i === 0 && replyToMessageId
                            ? { message_id: replyToMessageId }
                            : undefined,
                }
            )) as Message.TextMessage;

            sentMessages.push(sentMessage);
        }

        return sentMessages;
    }

    // Split message into smaller parts
    private splitMessage(text: string): string[] {
        const chunks: string[] = [];
        let currentChunk = "";

        const lines = text.split("\n");
        for (const line of lines) {
            if (currentChunk.length + line.length + 1 <= MAX_MESSAGE_LENGTH) {
                currentChunk += (currentChunk ? "\n" : "") + line;
            } else {
                if (currentChunk) chunks.push(currentChunk);
                currentChunk = line;
            }
        }

        if (currentChunk) chunks.push(currentChunk);
        return chunks;
    }

    // Generate a response using AI
    private async _generateResponse(
        message: Memory,
        state: State,
        context: string
    ): Promise<Content> {
        const { userId, roomId } = message;

        const response = await generateMessageResponse({
            runtime: this.runtime,
            context,
            modelClass: ModelClass.MEDIUM,
            modelOverride: "hyperbolic"
        });

        if (!response) {
            console.error("❌ No response from generateMessageResponse");
            return null;
        }
        await this.runtime.databaseAdapter.log({
            body: { message, context, response },
            userId: userId,
            roomId,
            type: "response",
        });

        return response;
    }

    // Main handler for incoming messages
    public async handleMessage(ctx: Context): Promise<void> {
        if (!ctx.message || !ctx.from) {
            return; // Exit if no message or sender info
        }

        // TODO: Handle commands?
        // if (ctx.message.text?.startsWith("/")) {
        //     return;
        // }

        const message = ctx.message;

        try {
            // Convert IDs to UUIDs
            const userId = stringToUuid(ctx.from.id.toString()) as UUID;
            const userName =
                ctx.from.username || ctx.from.first_name || "Unknown User";
            const chatId = stringToUuid(
                ctx.chat?.id.toString() + "-" + this.runtime.agentId
            ) as UUID;
            const agentId = this.runtime.agentId;
            const roomId = chatId;

            await this.runtime.ensureConnection(
                userId,
                roomId,
                userName,
                userName,
                "telegram"
            );

            const messageId = stringToUuid(
                message.message_id.toString() + "-" + this.runtime.agentId
            ) as UUID;

            // Handle images
            const imageInfo = await this.processImage(message);

            // Get text or caption
            let messageText = "";
            if ("text" in message) {
                messageText = message.text;
            } else if ("caption" in message && message.caption) {
                messageText = message.caption;
            }

            // Combine text and image description
            const fullText = imageInfo
                ? `${messageText} ${imageInfo.description}`
                : messageText;

            if (!fullText) {
                return; // Skip if no content
            }

            const content: Content = {
                text: fullText,
                source: "telegram",
                inReplyTo:
                    "reply_to_message" in message && message.reply_to_message
                        ? stringToUuid(
                              message.reply_to_message.message_id.toString() +
                                  "-" +
                                  this.runtime.agentId
                          )
                        : undefined,
            };

            // Create memory for the message
            const memory: Memory = {
                id: messageId,
                agentId,
                userId,
                roomId,
                content,
                createdAt: message.date * 1000,
                embedding: embeddingZeroVector,
            };

            await this.runtime.messageManager.createMemory(memory);

            // Update state with the new memory
            let state = await this.runtime.composeState(memory);
            state = await this.runtime.updateRecentMessageState(state);

            // Decide whether to respond
            const shouldRespond = await this._shouldRespond(message, state);
            if (shouldRespond) {
            // Generate response
            const context = composeContext({
                state,
                template:
                    this.runtime.character.templates
                        ?.telegramMessageHandlerTemplate ||
                    this.runtime.character?.templates?.messageHandlerTemplate ||
                    telegramMessageHandlerTemplate,
            });

            const responseContent = await this._generateResponse(
                memory,
                state,
                context
            );

            if (!responseContent || !responseContent.text) return;

            // Send response in chunks
            const callback: HandlerCallback = async (content: Content) => {
                const sentMessages = await this.sendMessageInChunks(
                    ctx,
                    content.text,
                    message.message_id
                );

                const memories: Memory[] = [];

                // Create memories for each sent message
                for (let i = 0; i < sentMessages.length; i++) {
                    const sentMessage = sentMessages[i];
                    const isLastMessage = i === sentMessages.length - 1;

                    const memory: Memory = {
                        id: stringToUuid(
                            sentMessage.message_id.toString() +
                                "-" +
                                this.runtime.agentId
                        ),
                        agentId,
                        userId,
                        roomId,
                        content: {
                            ...content,
                            text: sentMessage.text,
                            action: !isLastMessage ? "CONTINUE" : undefined,
                            inReplyTo: messageId,
                        },
                        createdAt: sentMessage.date * 1000,
                        embedding: embeddingZeroVector,
                    };

                    await this.runtime.messageManager.createMemory(memory);
                    memories.push(memory);
                }

                return memories;
            };

            // Execute callback to send messages and log memories
            const responseMessages = await callback(responseContent);

            // Update state after response
            state = await this.runtime.updateRecentMessageState(state);

            // Handle any resulting actions
            await this.runtime.processActions(
                memory,
                responseMessages,
                state,
                callback
            );
        }

            await this.runtime.evaluate(memory, state, shouldRespond);
        } catch (error) {
            console.error("❌ Error handling message:", error);
            console.error("Error sending message:", error);
        }
    }
}
