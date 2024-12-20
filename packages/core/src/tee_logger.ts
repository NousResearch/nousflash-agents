import fs from 'fs';
import path from 'path';
import { BlobServiceClient } from '@azure/storage-blob';
import { Character } from '@ai16z/eliza';
import { RotatingFileStream, createStream } from 'rotating-file-stream';
import crypto from 'crypto';

let accessLogStream: RotatingFileStream | null = null;

export function setup_teelogger(logDirectory: string, character: Character) {
    const logDirectory = path.join(process.cwd(), 'logs');
    fs.existsSync(logDirectory) || fs.mkdirSync(logDirectory);
    
    const accessLogStream = createStream(`agent-${character.name}.log`, {
        interval: '1m', // rotate hourly
        path: logDirectory,
        size: '10M', // rotate when size exceeds 10MB
        maxFiles: 7
    });
      
    // Store original console methods and create patched versions
    const methods = ['log', 'error', 'warn', 'info'] as const;
    const originalConsole = {} as Record<typeof methods[number], typeof console.log>;
      
    methods.forEach(method => {
        originalConsole[method] = console[method];
        console[method] = (...args) => {
            const message = args.map(arg => 
                typeof arg === 'object' ? JSON.stringify(arg) : arg
            ).join(' ');
            accessLogStream.write(`${new Date().toISOString()} [${method.toUpperCase()}] ${message}\n`);
            originalConsole[method].apply(console, args);
        };
    });
      
    // Install rotation handler
    accessLogStream.on('rotated', async (newFile: string) => {
        if (process.env.AZURE_BLOB_CONNECTION_STRING) {
            await handleLogRotation(character, newFile);
        }
        console.log(`Log rotated ${newFile}`);
    });

    return accessLogStream;
}

async function upload_to_azure(character: Character, filePath: string, isRedacted: boolean = false) {
    try {
        const blobServiceClient = BlobServiceClient.fromConnectionString(
            process.env.AZURE_BLOB_CONNECTION_STRING || ''
        );

        const containerName = isRedacted 
            ? 'agent-sanitized-logs-' + character.name.toLowerCase()
            : 'agent-logs-' + character.name.toLowerCase();
        const containerClient = blobServiceClient.getContainerClient(containerName);

        // Create container if it doesn't exist
        await containerClient.createIfNotExists();

        const blobName = `${character.name}/${path.basename(filePath)}`;
        const blockBlobClient = containerClient.getBlockBlobClient(blobName);
        
        await blockBlobClient.uploadFile(filePath);
        console.log(`Uploaded ${filePath} to Azure Blob Storage as ${blobName}`);
    } catch (error) {
        console.error('Error uploading log to Azure:', error);
    }
}

async function createSanitizedLog(filePath: string): Promise<string> {
    const content = await fs.promises.readFile(filePath, 'utf-8');
    const lines = content.split('\n');
    
    // Matches ISO timestamp, log level, and REDACTED: prefix
    const redactedLineRegex = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z \[[A-Z]+\] REDACT:/;
    
    return lines.map(line => {
        if (redactedLineRegex.test(line)) {
            const hash = crypto
                .createHash('sha256')
                .update(line)
                .digest('hex');
            
            // Find the position after "REDACTED:"
            const redactedPos = line.indexOf('REDACTED:') + 9;
            // Keep the prefix (timestamp, level, and "REDACTED:")
            const prefix = line.substring(0, redactedPos);
            
            // Calculate padding to match original line length
            const paddingLength = Math.max(0, line.length - (prefix.length + 64)); // 64 is length of sha256 hex
            const padding = '\u2800'.repeat(paddingLength); // Unicode Braille Pattern Blank

            return `${prefix} ${hash}${padding}`;
        }
        return line;
    }).join('\n');
}

async function handleLogRotation(character: Character, newFile: string) {
    try {
        // Upload original file
        await upload_to_azure(character, newFile);

        // Handle redacted version if enabled
        if (!process.env.ENABLE_LOG_REDACTION === 'false') {
            const sanitizedPath = newFile + '.sanitized';
            const sanitizedContent = await createSanitizedLog(newFile);
            await fs.promises.writeFile(sanitizedPath, sanitizedContent);

            // Upload sanitized version
            await upload_to_azure(character, sanitizedPath, true);

            // Clean up temporary sanitized file
            await fs.promises.unlink(sanitizedPath);
        }
    } catch (error) {
        console.error('Error handling log rotation:', error);
    }
}

setup_teelogger();
