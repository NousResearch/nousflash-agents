FROM node:23.1.0
# Install pnpm globally
RUN npm install -g pnpm@9.4.0

# Set the working directory
WORKDIR /app

# Add configuration files and install dependencies
ADD pnpm-workspace.yaml /app/pnpm-workspace.yaml
ADD package.json /app/package.json
ADD .npmrc /app/.npmrc
ADD tsconfig.json /app/tsconfig.json
ADD pnpm-lock.yaml /app/pnpm-lock.yaml
RUN pnpm i

# Add the documentation
# ADD docs /app/docs
# RUN pnpm i

# Add the rest of the application code
ADD packages /app/packages
RUN pnpm i

# Add the environment variables
ADD scripts /app/scripts
ADD characters /app/characters

# Build the application
RUN pnpm build

# Expose the port
EXPOSE 3000

# Start command
CMD ["pnpm", "dev"] 
# "--character=characters/dv.character.json"
