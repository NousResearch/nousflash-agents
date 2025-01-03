import { type Hex } from "viem";
import { Alchemy, Network } from "alchemy-sdk";

import {
    HandlerCallback,
    ModelClass,
    type IAgentRuntime,
    type Memory,
    type State,
} from "@ai16z/eliza/src/types.ts";

import { composeContext } from "@ai16z/eliza/src/context.ts";
import { generateObject } from "@ai16z/eliza/src/generation.ts";

import { initWalletProvider, WalletProvider } from "../providers/wallet.ts";
import { base } from "viem/chains";

const redeemTemplate = `Given the recent messages and wallet information below:

{{recentMessages}}

{{walletInfo}}

Extract the following information about the NFT redemption:
- Content: The content to be posted/liked

Respond with a JSON markdown block containing the extracted values:

\`\`\`json
{
    "content": string,
}
\`\`\`
`;

interface NFTMetadata {
    tokenId: number;
    policy: string;
    username: string;
    name: string;
}

interface RedeemParams {
    tokenId: number;
    content: string;
    type: "TWEET" | "LIKE";
}

export class RedeemNFTAction {
    private alchemy: Alchemy;

    constructor(private walletProvider: WalletProvider) {
        this.alchemy = new Alchemy({
            apiKey: process.env.ALCHEMY_API_KEY,
            network: Network.BASE_MAINNET,
        });
    }

    async getOwnedNFTs(address: string): Promise<NFTMetadata[]> {
        const contractAddress = "0xaa875a983746f2a5e9f7eccdc1bc988ca7ce4035";
        
        const nfts = await this.alchemy.nft.getNftsForOwner(address, {
            contractAddresses: [contractAddress]
        });

        return nfts.ownedNfts.map(nft => ({
            tokenId: Number(nft.tokenId),
            // Parse other metadata from nft.rawMetadata
            policy: nft.raw.metadata?.attributes?.find(attr => attr.trait_type === "LLM safeguard")?.value || "",
            username: nft.raw.metadata?.attributes?.find(attr => attr.trait_type === "X Username")?.value || "",
            name: nft.raw.metadata?.attributes?.find(attr => attr.trait_type === "X Name")?.value || "",
        }));
    }

    async redeemFirstAvailable(content: string): Promise<{ hash: Hex } | null> {
        const address = this.walletProvider.getWalletClient("base").account.address;
        const ownedNFTs = await this.getOwnedNFTs(address);
        
        if (ownedNFTs.length === 0) {
            console.log("No NFTs found for agent wallt:", address);
            return null;
        }

        // Use the first available NFT
        const nftToRedeem = ownedNFTs[0];
        
        return this.redeem({
            tokenId: nftToRedeem.tokenId,
            content,
            type: "TWEET"
        });
    }

    async redeem(params: RedeemParams): Promise<{ hash: Hex }> {
        console.log(
            `Redeeming NFT: Token ID ${params.tokenId} with content "${params.content}" as ${params.type}`
        );

        const walletClient = this.walletProvider.getWalletClient("base");
        const contractAddress = "0xaa875a983746f2a5e9f7eccdc1bc988ca7ce4035";

        try {
            // Create contract interface for the redeem function
            const hash = await walletClient.writeContract({
                account: walletClient.account,
                address: contractAddress as Hex,
                abi: [{
                    name: "redeem",
                    type: "function",
                    inputs: [
                        { name: "tokenId", type: "uint256" },
                        { name: "content", type: "string" },
                        { name: "tokenType", type: "uint8" }
                    ],
                    outputs: [],
                    stateMutability: "nonpayable"
                }],
                functionName: "redeem",
                args: [
                    BigInt(params.tokenId),
                    params.content,
                    0
                ],
                chain: base,
            });

            return { hash };
        } catch (error) {
            throw new Error(`NFT redemption failed: ${error.message}`);
        }
    }
}

const buildRedeemDetails = async (
    state: State,
    runtime: IAgentRuntime
): Promise<RedeemParams> => {
    const context = composeContext({
        state,
        template: redeemTemplate,
    });

    const redeemDetails = (await generateObject({
        runtime,
        context,
        modelClass: ModelClass.SMALL,
    })) as RedeemParams;

    return redeemDetails;
};

export const redeemNFTAction = {
    name: "redeemNFT",
    description: "Redeem an NFT token to post a tweet or like",
    handler: async (
        runtime: IAgentRuntime,
        _message: Memory,
        state: State,
        _options: any,
        callback?: HandlerCallback
    ) => {
        console.log("Redeem NFT action handler called");
        const walletProvider = initWalletProvider(runtime);
        const action = new RedeemNFTAction(walletProvider);

        const address = walletProvider.getWalletClient("base").account.address;

        const paramOptions = await buildRedeemDetails(state, runtime);

        try {
            const redeemResp = await action.redeemFirstAvailable(
                paramOptions.content
            );
            if (!redeemResp) {
                if (callback) {
                    callback({
                        text: "No available NFTs found to redeem",
                        content: { success: false, error: "No NFTs available" },
                    });
                }
                return false;
            }
            // const redeemResp = await action.redeem(paramOptions);
            if (callback) {
                callback({
                    text: `Successfully redeemed Teleport NFTwith transaction hash: ${redeemResp.hash}`,
                    content: {
                        success: true,
                        hash: redeemResp.hash,
                        chain: base,
                    },
                });
            }
            return true;
        } catch (error) {
            console.error("Error during NFT redemption:", error);
            if (callback) {
                callback({
                    text: `Error redeeming NFT: ${error.message}`,
                    content: { error: error.message },
                });
            }
            return false;
        }
    },
    template: redeemTemplate,
    validate: async (runtime: IAgentRuntime) => {
        const privateKey = runtime.getSetting("EVM_PRIVATE_KEY");
        return typeof privateKey === "string" && privateKey.startsWith("0x");
    },
    examples: [
        [
            {
                user: "assistant",
                content: {
                    text: "I'll help you redeem your NFT to post a tweet",
                    action: "REDEEM_NFT",
                },
            },
            {
                user: "user",
                content: {
                    text: "Redeem an NFT to post 'Hello World!'",
                    action: "REDEEM_NFT",
                },
            },
        ],
    ],
    similes: ["REDEEM_NFT", "USE_NFT", "BURN_NFT"],
};