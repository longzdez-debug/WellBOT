FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY tsconfig.json ./
COPY src ./src
RUN npm run build

# Copy SQL schema file to dist
RUN cp src/database/schema.sql dist/database/

# Remove dev dependencies after build
RUN npm prune --production

CMD ["node", "dist/index.js"]
