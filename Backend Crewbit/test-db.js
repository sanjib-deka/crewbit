import mongoose from "mongoose";
import dotenv from "dotenv";

dotenv.config();

const uri = process.env.MONGO_URL;

if (!uri) {
    console.error("❌ MONGO_URL not found in .env file");
    process.exit(1);
}

// Mask password for safe logging
const maskedUri = uri.replace(/\/\/(.*):(.*)@/, (match, user, pass) => {
    return `//${user}:******@`;
});

console.log(`🔍 Attempting to connect to: ${maskedUri}`);

async function testConnection() {
    try {
        await mongoose.connect(uri, {
            serverSelectionTimeoutMS: 5000, // Timeout after 5 seconds
        });
        console.log("✅ Database Connected Successfully!");
        process.exit(0);
    } catch (error) {
        console.error("❌ Connection failed!");
        if (error.message.includes("authentication failed")) {
            console.error("\n[Possible Causes]");
            console.error("1. Incorrect username or password in .env");
            console.error("2. IP address not whitelisted in MongoDB Atlas");
            console.error("3. Database user 'AI-HR' lacks appropriate permissions in Atlas");
        }
        console.error("\n[Error Details]");
        console.error(error);
        process.exit(1);
    }
}

testConnection();
