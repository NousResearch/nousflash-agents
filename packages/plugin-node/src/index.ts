import { Plugin } from "@ai16z/eliza/src/types.ts";
import { BrowserService } from "./services/browser.ts";
import { PdfService } from "./services/pdf.ts";
import { TranscriptionService } from "./services/transcription.ts";
import { VideoService } from "./services/video.ts";

export const nodePlugin: Plugin = {
    name: "default",
    description: "Default plugin, with basic actions and evaluators",
    services: [
        BrowserService,
        PdfService,
        TranscriptionService,
        VideoService,
    ],
};

export default nodePlugin;
