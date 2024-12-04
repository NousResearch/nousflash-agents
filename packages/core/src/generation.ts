import { createAnthropic } from "@ai-sdk/anthropic";
import { createGroq } from "@ai-sdk/groq";
import { createOpenAI } from "@ai-sdk/openai";
import { getModel } from "./models.ts";
import { IImageDescriptionService, ModelClass, ActionResponse } from "./types.ts";
import { generateText as aiGenerateText } from "ai";
import { Buffer } from "buffer";
import OpenAI from "openai";
import { default as tiktoken, TiktokenModel } from "tiktoken";
import Together from "together-ai";
import { elizaLogger } from "./index.ts";
import models from "./models.ts";
import { createGoogleGenerativeAI } from "@ai-sdk/google";
import {
    parseBooleanFromText,
    parseJsonArrayFromText,
    parseJSONObjectFromText,
    parseShouldRespondFromText,
    parseActionResponseFromText,
} from "./parsing.ts";
import settings from "./settings.ts";
import {
    Content,
    IAgentRuntime,
    ITextGenerationService,
    ModelProviderName,
    ServiceType,
} from "./types.ts";

import { BASE_FORMAT_PROMPT, FORMAT_SYSTEM_PROMPT } from "./prompts.ts";
import { defaultCharacter } from "./defaultCharacter.ts";
import { parse } from "path";


/**
 * Send a message to the model for a text generateText - receive a string back and parse how you'd like
 * @param opts - The options for the generateText request.
 * @param opts.context The context of the message to be completed.
 * @param opts.stop A list of strings to stop the generateText at.
 * @param opts.model The model to use for generateText.
 * @param opts.frequency_penalty The frequency penalty to apply to the generateText.
 * @param opts.presence_penalty The presence penalty to apply to the generateText.
 * @param opts.temperature The temperature to apply to the generateText.
 * @param opts.max_context_length The maximum length of the context to apply to the generateText.
 * @returns The completed message.
 */

export async function generateText({
    runtime,
    context,
    modelClass,
    stop,
    modelOverride
}: {
    runtime: IAgentRuntime;
    context: string;
    modelClass: string;
    stop?: string[];
    modelOverride?: string;
}): Promise<string> {
    if (!context) {
        console.error("generateText context is empty");
        return "";
    }

    let providerCheck;
    if (modelOverride) {
        providerCheck = modelOverride;
    }
    else {
        providerCheck = runtime.modelProvider;
        console.debug(`Provider Check during generateText ${providerCheck}`)
    }

    const provider = providerCheck;
    const endpoint =
        runtime.character.modelEndpointOverride || models[provider].endpoint;
    const model = models[provider].model[modelClass];
    const temperature = models[provider].settings.temperature;
    const frequency_penalty = models[provider].settings.frequency_penalty;
    const presence_penalty = models[provider].settings.presence_penalty;
    const max_context_length = models[provider].settings.maxInputTokens;
    const max_response_length = models[provider].settings.maxOutputTokens;

    const apiKey = runtime.token;
    console.debug(`generateText vars initialized`)

    try {
        console.debug(
            `Trimming context to max length of ${max_context_length} tokens.`
        );
        context = await trimTokens(context, max_context_length, "gpt-4o");

        let response: string;

        const _stop = stop || models[provider].settings.stop;
        console.debug(
            `Using provider: ${provider}, model: ${model}, temperature: ${temperature}, max response length: ${max_response_length}`
        );

        switch (provider) {
            case ModelProviderName.OPENAI:
            case ModelProviderName.LLAMACLOUD: {
                elizaLogger.debug("Initializing OpenAI model.");
                const openai = createOpenAI({ apiKey, baseURL: endpoint });

                const { text: openaiResponse } = await aiGenerateText({
                    model: openai.languageModel(model),
                    prompt: context,
                    system:
                        runtime.character.system ??
                        settings.SYSTEM_PROMPT ??
                        undefined,
                    temperature: temperature,
                    maxTokens: max_response_length,
                    frequencyPenalty: frequency_penalty,
                    presencePenalty: presence_penalty,
                });

                response = openaiResponse;
                elizaLogger.debug("Received response from OpenAI model.");
                break;
            }

            case ModelProviderName.GOOGLE:
                { const google = createGoogleGenerativeAI();

                const { text: anthropicResponse } = await aiGenerateText({
                    model: google(model),
                    prompt: context,
                    system:
                        runtime.character.system ??
                        settings.SYSTEM_PROMPT ??
                        undefined,
                    temperature: temperature,
                    maxTokens: max_response_length,
                    frequencyPenalty: frequency_penalty,
                    presencePenalty: presence_penalty,
                });

                response = anthropicResponse;
                break; }

            case ModelProviderName.ANTHROPIC: {
                elizaLogger.debug("Initializing Anthropic model.");

                const anthropic = createAnthropic({ apiKey });

                const { text: anthropicResponse } = await aiGenerateText({
                    model: anthropic.languageModel(model),
                    prompt: context,
                    system:
                        runtime.character.system ??
                        settings.SYSTEM_PROMPT ??
                        undefined,
                    temperature: temperature,
                    maxTokens: max_response_length,
                    frequencyPenalty: frequency_penalty,
                    presencePenalty: presence_penalty,
                });

                response = anthropicResponse;
                elizaLogger.debug("Received response from Anthropic model.");
                break;
            }

            case ModelProviderName.GROK: {
                elizaLogger.debug("Initializing Grok model.");
                const grok = createOpenAI({ apiKey, baseURL: endpoint });

                const { text: grokResponse } = await aiGenerateText({
                    model: grok.languageModel(model, {
                        parallelToolCalls: false,
                    }),
                    prompt: context,
                    system:
                        runtime.character.system ??
                        settings.SYSTEM_PROMPT ??
                        undefined,
                    temperature: temperature,
                    maxTokens: max_response_length,
                    frequencyPenalty: frequency_penalty,
                    presencePenalty: presence_penalty,
                });

                response = grokResponse;
                elizaLogger.debug("Received response from Grok model.");
                break;
            }

            case ModelProviderName.GROQ: {
                console.log("Initializing Groq model.");
                const groq = createGroq({ apiKey });

                const { text: groqResponse } = await aiGenerateText({
                    model: groq.languageModel(model),
                    prompt: context,
                    temperature: temperature,
                    system:
                        runtime.character.system ??
                        settings.SYSTEM_PROMPT ??
                        undefined,
                    maxTokens: max_response_length,
                    frequencyPenalty: frequency_penalty,
                    presencePenalty: presence_penalty,
                });

                response = groqResponse;
                console.log("Received response from Groq model.");
                break;
            }

            case ModelProviderName.REDPILL: {
                elizaLogger.debug("Initializing RedPill model.");
                const serverUrl = models[provider].endpoint;
                const openai = createOpenAI({ apiKey, baseURL: serverUrl });

                const { text: openaiResponse } = await aiGenerateText({
                    model: openai.languageModel(model),
                    prompt: context,
                    temperature: temperature,
                    system:
                        runtime.character.system ??
                        settings.SYSTEM_PROMPT ??
                        undefined,
                    maxTokens: max_response_length,
                    frequencyPenalty: frequency_penalty,
                    presencePenalty: presence_penalty,
                });

                response = openaiResponse;
                elizaLogger.debug("Received response from OpenAI model.");
                break;
            }

            case ModelProviderName.OPENROUTER: {
                elizaLogger.debug("Initializing OpenRouter model.");
                const serverUrl = models[provider].endpoint;
                const openrouter = createOpenAI({ apiKey: settings.OPENROUTER_API_KEY, baseURL: serverUrl });

                const { text: openrouterResponse } = await aiGenerateText({
                    model: openrouter.languageModel(model),
                    prompt: context,
                    temperature: temperature,
                    system:
                        runtime.character.system ??
                        settings.SYSTEM_PROMPT ??
                        undefined,
                    maxTokens: max_response_length,
                    frequencyPenalty: frequency_penalty,
                    presencePenalty: presence_penalty,
                });

                response = openrouterResponse;
                elizaLogger.debug("Received response from OpenRouter model.");
                break;
            }

            case ModelProviderName.HYPERBOLIC:
                if(modelClass === ModelClass.SMALL) {
                    console.debug("Initializing Hyperbolic Small model for posting.");
                    response = await generateFormatCompletion(context, runtime.character.system);

                    break;
                }
                if(modelClass === ModelClass.MEDIUM) {
                    console.debug("Initializing Hyperbolic Medium model for posting.");
                    response = await generateFormatCompletion(context, runtime.character.system);

                    break;
                }
                if (modelClass === ModelClass.LARGE) {

                    console.debug("Initializing Hyperbolic Based model for posting.");
                    response = await generateBaseCompletion(context);
                    console.debug("Received response from Hyperbolic base model.");

                    break;
                }
                
            default: {
                const errorMessage = `Unsupported provider: ${provider}`;
                elizaLogger.error(errorMessage);
                throw new Error(errorMessage);
            }
        }

        return response;
    } catch (error) {
        elizaLogger.error("Error in generateText:", error);
        throw error;
    }
}

/**
 * Truncate the context to the maximum length allowed by the model.
 * @param model The model to use for generateText.
 * @param context The context of the message to be completed.
 * @param max_context_length The maximum length of the context to apply to the generateText.
 * @returns
 */
export function trimTokens(context, maxTokens, model) {
    // Count tokens and truncate context if necessary
    const encoding = tiktoken.encoding_for_model(model as TiktokenModel);
    let tokens = encoding.encode(context);
    const textDecoder = new TextDecoder();
    if (tokens.length > maxTokens) {
        tokens = tokens.reverse().slice(maxTokens).reverse();

        context = textDecoder.decode(encoding.decode(tokens));
    }
    return context;
}
/**
 * Sends a message to the model to determine if it should respond to the given context.
 * @param opts - The options for the generateText request
 * @param opts.context The context to evaluate for response
 * @param opts.stop A list of strings to stop the generateText at
 * @param opts.model The model to use for generateText
 * @param opts.frequency_penalty The frequency penalty to apply (0.0 to 2.0)
 * @param opts.presence_penalty The presence penalty to apply (0.0 to 2.0)
 * @param opts.temperature The temperature to control randomness (0.0 to 2.0)
 * @param opts.serverUrl The URL of the API server
 * @param opts.max_context_length Maximum allowed context length in tokens
 * @param opts.max_response_length Maximum allowed response length in tokens
 * @returns Promise resolving to "RESPOND", "IGNORE", "STOP" or null
 */
export async function generateShouldRespond({
    runtime,
    context,
    modelClass,
}: {
    runtime: IAgentRuntime;
    context: string;
    modelClass: string;
}): Promise<"RESPOND" | "IGNORE" | "STOP" | null> {
    let retryDelay = 1000;
    while (true) {
        try {
            console.debug(
                "Attempting to generate text with context for response:",
                context
            );
            const response = await generateText({
                runtime,
                context,
                modelClass,
            });
            
            // console.debug("Received response from generateText:", response);
            const parsedResponse = parseShouldRespondFromText(response.trim());
            if (parsedResponse) {
                console.debug("Parsed response:", parsedResponse);
                return parsedResponse;
            } else {
                // elizaLogger.debug("generateShouldRespond no response");
            }
        } catch (error) {
            elizaLogger.error("Error in generateShouldRespond:", error);
            if (
                error instanceof TypeError &&
                error.message.includes("queueTextCompletion")
            ) {
                elizaLogger.error(
                    "TypeError: Cannot read properties of null (reading 'queueTextCompletion')"
                );
            }
        }

        elizaLogger.log(`Retrying in ${retryDelay}ms...`);
        await new Promise((resolve) => setTimeout(resolve, retryDelay));
        retryDelay *= 2;
    }
}

export async function generateTweetActions({
    runtime,
    context,
    modelClass,
    modelOverride,
}: {
    runtime: IAgentRuntime;
    context: string;
    modelClass: string;
    modelOverride?: string;
}): Promise<ActionResponse | null> {
    let retryDelay = 1000;
    
    while (true) {
        try {
            // console.debug(
            //     "Attempting to generate text with context for tweet actions:",
            //     context
            // );
            console.debug("Attempting to generate text with context for tweet actions")
            
            const response = await generateText({
                runtime,
                context,
                modelClass,
                modelOverride,
            });
            
            // console.debug("Received response from generateText for tweet actions:", response);
            const { actions } = parseActionResponseFromText(response.trim());
            
            if (actions) {
                console.debug("Parsed tweet actions:", actions);
                return actions;
            } else {
                elizaLogger.debug("generateTweetActions no valid response");
            }
        } catch (error) {
            elizaLogger.error("Error in generateTweetActions:", error);
            if (
                error instanceof TypeError &&
                error.message.includes("queueTextCompletion")
            ) {
                elizaLogger.error(
                    "TypeError: Cannot read properties of null (reading 'queueTextCompletion')"
                );
            }
        }

        elizaLogger.log(`Retrying in ${retryDelay}ms...`);
        await new Promise((resolve) => setTimeout(resolve, retryDelay));
        retryDelay *= 2;
    }
}



/**
 * Splits content into chunks of specified size with optional overlapping bleed sections
 * @param content - The text content to split into chunks
 * @param chunkSize - The maximum size of each chunk in tokens
 * @param bleed - Number of characters to overlap between chunks (default: 100)
 * @param model - The model name to use for tokenization (default: runtime.model)
 * @returns Promise resolving to array of text chunks with bleed sections
 */
export async function splitChunks(
    runtime,
    content: string,
    chunkSize: number,
    bleed: number = 100,
    modelClass: string
): Promise<string[]> {
    const model = models[runtime.modelProvider];
    console.log("model", model);

    console.log("model.model.embedding", model.model.embedding);
    
    if(!model.model.embedding) {
        throw new Error("Model does not support embedding");
    }

    const encoding = tiktoken.encoding_for_model(
        model.model.embedding as TiktokenModel
    );
    const tokens = encoding.encode(content);
    const chunks: string[] = [];
    const textDecoder = new TextDecoder();

    for (let i = 0; i < tokens.length; i += chunkSize) {
        const chunk = tokens.slice(i, i + chunkSize);
        const decodedChunk = textDecoder.decode(encoding.decode(chunk));

        // Append bleed characters from the previous chunk
        const startBleed = i > 0 ? content.slice(i - bleed, i) : "";
        // Append bleed characters from the next chunk
        const endBleed =
            i + chunkSize < tokens.length
                ? content.slice(i + chunkSize, i + chunkSize + bleed)
                : "";

        chunks.push(startBleed + decodedChunk + endBleed);
    }

    return chunks;
}

/**
 * Sends a message to the model and parses the response as a boolean value
 * @param opts - The options for the generateText request
 * @param opts.context The context to evaluate for the boolean response
 * @param opts.stop A list of strings to stop the generateText at
 * @param opts.model The model to use for generateText
 * @param opts.frequency_penalty The frequency penalty to apply (0.0 to 2.0)
 * @param opts.presence_penalty The presence penalty to apply (0.0 to 2.0)
 * @param opts.temperature The temperature to control randomness (0.0 to 2.0)
 * @param opts.serverUrl The URL of the API server
 * @param opts.token The API token for authentication
 * @param opts.max_context_length Maximum allowed context length in tokens
 * @param opts.max_response_length Maximum allowed response length in tokens
 * @returns Promise resolving to a boolean value parsed from the model's response
 */
export async function generateTrueOrFalse({
    runtime,
    context = "",
    modelClass,
}: {
    runtime: IAgentRuntime;
    context: string;
    modelClass: string;
}): Promise<boolean> {
    let retryDelay = 1000;
    console.log("modelClass", modelClass);

    const stop = Array.from(
        new Set([
            ...(models[runtime.modelProvider].settings.stop || []),
            ["\n"],
        ])
    ) as string[];

    while (true) {
        try {
            const response = await generateText({
                stop,
                runtime,
                context,
                modelClass,
            });

            const parsedResponse = parseBooleanFromText(response.trim());
            if (parsedResponse !== null) {
                return parsedResponse;
            }
        } catch (error) {
            elizaLogger.error("Error in generateTrueOrFalse:", error);
        }

        await new Promise((resolve) => setTimeout(resolve, retryDelay));
        retryDelay *= 2;
    }
}

/**
 * Send a message to the model and parse the response as a string array
 * @param opts - The options for the generateText request
 * @param opts.context The context/prompt to send to the model
 * @param opts.stop Array of strings that will stop the model's generation if encountered
 * @param opts.model The language model to use
 * @param opts.frequency_penalty The frequency penalty to apply (0.0 to 2.0)
 * @param opts.presence_penalty The presence penalty to apply (0.0 to 2.0)
 * @param opts.temperature The temperature to control randomness (0.0 to 2.0)
 * @param opts.serverUrl The URL of the API server
 * @param opts.token The API token for authentication
 * @param opts.max_context_length Maximum allowed context length in tokens
 * @param opts.max_response_length Maximum allowed response length in tokens
 * @returns Promise resolving to an array of strings parsed from the model's response
 */
export async function generateTextArray({
    runtime,
    context,
    modelClass,
}: {
    runtime: IAgentRuntime;
    context: string;
    modelClass: string;
}): Promise<string[]> {
    if (!context) {
        elizaLogger.error("generateTextArray context is empty");
        return [];
    }
    let retryDelay = 1000;

    while (true) {
        try {
            const response = await generateText({
                runtime,
                context,
                modelClass,
            });

            const parsedResponse = parseJsonArrayFromText(response);
            if (parsedResponse) {
                return parsedResponse;
            }
        } catch (error) {
            elizaLogger.error("Error in generateTextArray:", error);
        }

        await new Promise((resolve) => setTimeout(resolve, retryDelay));
        retryDelay *= 2;
    }
}

export async function generateObject({
    runtime,
    context,
    modelClass,
}: {
    runtime: IAgentRuntime;
    context: string;
    modelClass: string;
}): Promise<any> {
    if (!context) {
        elizaLogger.error("generateObject context is empty");
        return null;
    }
    let retryDelay = 1000;

    while (true) {
        try {
            // this is slightly different than generateObjectArray, in that we parse object, not object array
            const response = await generateText({
                runtime,
                context,
                modelClass,
            });
            const parsedResponse = parseJSONObjectFromText(response);
            if (parsedResponse) {
                return parsedResponse;
            }
        } catch (error) {
            elizaLogger.error("Error in generateObject:", error);
        }

        await new Promise((resolve) => setTimeout(resolve, retryDelay));
        retryDelay *= 2;
    }
}

export async function generateObjectArray({
    runtime,
    context,
    modelClass,
}: {
    runtime: IAgentRuntime;
    context: string;
    modelClass: string;
}): Promise<any[]> {
    if (!context) {
        elizaLogger.error("generateObjectArray context is empty");
        return [];
    }
    let retryDelay = 1000;

    while (true) {
        try {
            const response = await generateText({
                runtime,
                context,
                modelClass,
            });

            const parsedResponse = parseJsonArrayFromText(response);
            if (parsedResponse) {
                return parsedResponse;
            }
        } catch (error) {
            elizaLogger.error("Error in generateTextArray:", error);
        }

        await new Promise((resolve) => setTimeout(resolve, retryDelay));
        retryDelay *= 2;
    }
}

/**
 * Send a message to the model for generateText.
 * @param opts - The options for the generateText request.
 * @param opts.context The context of the message to be completed.
 * @param opts.stop A list of strings to stop the generateText at.
 * @param opts.model The model to use for generateText.
 * @param opts.frequency_penalty The frequency penalty to apply to the generateText.
 * @param opts.presence_penalty The presence penalty to apply to the generateText.
 * @param opts.temperature The temperature to apply to the generateText.
 * @param opts.max_context_length The maximum length of the context to apply to the generateText.
 * @returns The completed message.
 */
export async function generateMessageResponse({
    runtime,
    context,
    modelClass,
    modelOverride,
}: {
    runtime: IAgentRuntime;
    context: string;
    modelClass: string;
    modelOverride?: string;
}): Promise<Content> {
    const max_context_length =
        models[runtime.modelProvider].settings.maxInputTokens;
    context = trimTokens(context, max_context_length, "gpt-4o");
    let retryLength = 1000; // exponential backoff
    while (true) {
        try {
            let response;
            if (modelOverride) {
                response = await generateText({
                    runtime,
                    context,
                    modelClass,
                    modelOverride
                });
                console.log(`Reply generating with modelOverride: ${modelOverride}`);
            }
            else{
                response = await generateText({
                    runtime,
                    context,
                    modelClass,
                });
            }
            // try parsing the response as JSON, if null then try again
            const parsedContent = parseJSONObjectFromText(response) as Content;
            if (!parsedContent) {
                elizaLogger.debug("parsedContent is null, retrying");
                continue;
            }
            console.log(`Reply generated as: ${parsedContent.text}`);
            return parsedContent;
        } catch (error) {
            elizaLogger.error("ERROR:", error);
            // wait for 2 seconds
            retryLength *= 2;
            await new Promise((resolve) => setTimeout(resolve, retryLength));
            elizaLogger.debug("Retrying...");
        }
    }
}

export const generateImage = async (
    data: {
        prompt: string;
        width: number;
        height: number;
        count?: number;
    },
    runtime: IAgentRuntime
): Promise<{
    success: boolean;
    data?: string[];
    error?: any;
}> => {
    const { prompt, width, height } = data;
    let { count } = data;
    if (!count) {
        count = 1;
    }

    const model = getModel(runtime.character.modelProvider, ModelClass.IMAGE);
    const modelSettings = models[runtime.character.modelProvider].imageSettings;
    // some fallbacks for backwards compat, should remove in the future
    const apiKey =
        runtime.token ??
        runtime.getSetting("TOGETHER_API_KEY") ??
        runtime.getSetting("OPENAI_API_KEY");

    try {
        if (runtime.character.modelProvider === ModelProviderName.LLAMACLOUD) {
            const together = new Together({ apiKey: apiKey as string });
            const response = await together.images.create({
                model: "black-forest-labs/FLUX.1-schnell",
                prompt,
                width,
                height,
                steps: modelSettings?.steps ?? 4,
                n: count,
            });
            const urls: string[] = [];
            for (let i = 0; i < response.data.length; i++) {
                const json = response.data[i].b64_json;
                // decode base64
                const base64 = Buffer.from(json, "base64").toString("base64");
                urls.push(base64);
            }
            const base64s = await Promise.all(
                urls.map(async (url) => {
                    const response = await fetch(url);
                    const blob = await response.blob();
                    const buffer = await blob.arrayBuffer();
                    let base64 = Buffer.from(buffer).toString("base64");
                    base64 = "data:image/jpeg;base64," + base64;
                    return base64;
                })
            );
            return { success: true, data: base64s };
        } else {
            let targetSize = `${width}x${height}`;
            if (
                targetSize !== "1024x1024" &&
                targetSize !== "1792x1024" &&
                targetSize !== "1024x1792"
            ) {
                targetSize = "1024x1024";
            }
            const openai = new OpenAI({ apiKey: apiKey as string });
            const response = await openai.images.generate({
                model,
                prompt,
                size: targetSize as "1024x1024" | "1792x1024" | "1024x1792",
                n: count,
                response_format: "b64_json",
            });
            const base64s = response.data.map(
                (image) => `data:image/png;base64,${image.b64_json}`
            );
            return { success: true, data: base64s };
        }
    } catch (error) {
        console.error(error);
        return { success: false, error: error };
    }
};

export const generateCaption = async (
    data: { imageUrl: string },
    runtime: IAgentRuntime
): Promise<{
    title: string;
    description: string;
}> => {
    const { imageUrl } = data;
    const resp = await runtime
        .getService<IImageDescriptionService>(ServiceType.IMAGE_DESCRIPTION)
        .describeImage(imageUrl);
    return {
        title: resp.title.trim(),
        description: resp.description.trim(),
    };
};


interface HyperbolicResponse {
    choices: Array<{
      text: string;
    }>;
  }
  
  interface ChatResponse {
    choices: Array<{
      message: {
        content: string;
      };
    }>;
  }
  
  

  
  async function delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
  
  async function generateBaseCompletion(
    prompt: string,
    maxAttempts: number = 3
  ): Promise<string> {
    // First generate base model output
    let baseModelOutput = '';
      
    // Environment variable check
    if (!settings.HYPERBOLIC_API_KEY) {
      throw new Error('HYPERBOLIC_API_KEY environment variable is not set');
    }
    
    const HYPERBOLIC_API_KEY = settings.HYPERBOLIC_API_KEY;
    
    for (let tries = 0; tries < maxAttempts; tries++) {
      try {
        const response = await fetch("https://api.hyperbolic.xyz/v1/completions", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${HYPERBOLIC_API_KEY}`,
          },
          body: JSON.stringify({
            prompt: prompt,
            model: "meta-llama/Meta-Llama-3.1-405B",
            max_tokens: 512,
            temperature: 1,
            top_p: 0.95,
            top_k: 40,
            stop: ["<|im_end|>", "<"]
          })
        });
  
        if (response.ok) {
          const data: HyperbolicResponse = await response.json();
          const content = data.choices[0]?.text;
          
          console.debug(`Base completion data: ${data.choices[0].text}`)
          if (content?.trim()) {
            console.log(`Base model generated with response: ${content}`);
            baseModelOutput = content;
            break;
          }
        }
  
      } catch (error) {
        console.error(`Error on base model attempt ${tries + 1}:`, error);
        if (tries === maxAttempts - 1) {
          throw error;
        }
        await delay(1000); // 1 second delay between retries
      }
    }
  
    // Now format the tweet using the chat completion endpoint
    for (let tries = 0; tries < maxAttempts; tries++) {
      try {
        const response = await fetch("https://api.hyperbolic.xyz/v1/chat/completions", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${HYPERBOLIC_API_KEY}`,
          },
          body: JSON.stringify({
            messages: [
              {
                role: "system",
                content: BASE_FORMAT_PROMPT
              },
              {
                role: "user",
                content: `Here is the tweet: ${baseModelOutput}`
              }
            ],
            model: "meta-llama/Meta-Llama-3.1-70B-Instruct",
            max_tokens: 250,
            temperature: 1,
            top_p: 0.95,
            top_k: 40,
            stream: false
          })
        });
  
        if (response.ok) {
          const data: ChatResponse = await response.json();
          const content = data.choices[0]?.message?.content;
          
          if (content?.trim()) {
            console.log(`Formatted tweet: ${content}`);
            return content;
          }
        }
  
      } catch (error) {
        console.error(`Error on tweet formatting attempt ${tries + 1}:`, error);
        if (tries === maxAttempts - 1) {
          throw error;
        }
        await delay(1000); // 1 second delay between retries
      }
    }
    
    throw new Error("Failed to generate and format tweet after maximum attempts");
  }
  

  


  export async function generateFormatCompletion(
    base_input: string,
    prompt?: string,
    maxAttempts: number = 3
): Promise<string> {
    // Environment variable check
    if (!settings.HYPERBOLIC_API_KEY) {
        throw new Error('HYPERBOLIC_API_KEY environment variable is not set');
    }
    
    const HYPERBOLIC_API_KEY = settings.HYPERBOLIC_API_KEY;
    
    if(!prompt) {
        prompt = FORMAT_SYSTEM_PROMPT;
    }

    async function makeCompletionRequest(model: string, attempt: number): Promise<string | null> {
        try {
            console.debug(`Attempting to format tweet with model ${model} (attempt ${attempt + 1})`);
            
            const response = await fetch("https://api.hyperbolic.xyz/v1/chat/completions", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${HYPERBOLIC_API_KEY}`,
                },
                body: JSON.stringify({
                    messages: [
                        {
                            role: "system",
                            content: prompt
                        },
                        {
                            role: "user",
                            content: `Here is the tweet: ${base_input}`
                        }
                    ],
                    model: model,
                    max_tokens: 250,
                    temperature: 1,
                    top_p: 0.95,
                    top_k: 40,
                    stream: false
                })
            });

            if (response.ok) {
                const data: ChatResponse = await response.json();
                const content = data.choices[0]?.message?.content;
                
                if (content?.trim()) {
                    console.log(`Successfully formatted tweet with model ${model}: ${content}`);
                    return content;
                }
            }
            return null;
        } catch (error) {
            console.error(`Error with model ${model} on attempt ${attempt + 1}:`, error);
            return null;
        }
    }

    // Try with 405B model first
    const model405B = "meta-llama/Meta-Llama-3.1-405B-Instruct";
    for (let tries = 0; tries < maxAttempts; tries++) {
        const result = await makeCompletionRequest(model405B, tries);
        if (result) return result;
        
        if (tries < maxAttempts - 1) {
            await delay(1000); // 1 second delay between retries
        }
    }

    // If 405B failed after all attempts, try with 70B model
    console.log("Falling back to 70B model after 405B model failed all attempts");
    const model70B = "meta-llama/Meta-Llama-3.1-70B-Instruct";
    
    for (let tries = 0; tries < maxAttempts; tries++) {
        const result = await makeCompletionRequest(model70B, tries);
        if (result) return result;
        
        if (tries < maxAttempts - 1) {
            await delay(1000);
        }
    }

    // If both models fail after all attempts, throw error
    throw new Error("Failed to format tweet with both 405B and 70B models after all retry attempts");
}