// export * from "./actions/transfer";
// export * from "./providers/wallet";
// export * from "./types";

import { Plugin } from "@ai16z/eliza/src/types.ts";
import { transferAction } from "./actions/transfer.ts";
import { redeemNFTAction } from "./actions/redeem.ts";
import { evmWalletProvider } from "./providers/wallet.ts";

export const evmPlugin: Plugin = {
    name: "evm",
    description: "EVM blockchain integration plugin",
    providers: [evmWalletProvider],
    evaluators: [],
    services: [],
    actions: [transferAction, redeemNFTAction],
};

export default evmPlugin;
