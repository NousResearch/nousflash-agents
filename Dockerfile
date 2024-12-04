# FROM node:23.1.0

# RUN npm install -g pnpm@9.12.3

# WORKDIR /app

# COPY . .
# RUN pnpm clean
# RUN pnpm i
# RUN pnpm build

# EXPOSE 3007

# CMD ["pnpm", "dev"]


FROM node:23.1.0
# Install pnpm globally
RUN npm install -g pnpm@9.12.3

# Set the working directory
WORKDIR /app

# Add configuration files and install dependencies
ADD pnpm-workspace.yaml /app/pnpm-workspace.yaml
ADD package.json /app/package.json
ADD .npmrc /app/.npmrc
ADD tsconfig.json /app/tsconfig.json
ADD pnpm-lock.yaml /app/pnpm-lock.yaml
RUN pnpm i

# Add the rest of the application code
ADD packages /app/packages
RUN pnpm i

# Add the environment variables
ADD scripts /app/scripts
ADD characters /app/characters
ADD .env /app/.env

RUN pnpm build

EXPOSE 3007

CMD ["pnpm", "dev"]