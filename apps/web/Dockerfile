FROM node:20-alpine
WORKDIR /app
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL NEXT_TELEMETRY_DISABLED=1
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build && chown -R node /app
USER node
EXPOSE 3000
CMD ["npm", "start"]
