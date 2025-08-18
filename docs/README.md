# AI Slop Detection - Documentation

This directory contains comprehensive documentation for the AI Slop Detection browser extension project.

## 📚 Available Documentation

### Component Guides
- **[Backend Guide](backend-guide.md)** - Complete FastAPI backend development guide
- **[Extension Guide](extension-guide.md)** - Chrome extension development and architecture
- **[Database Schema](database-schema.md)** - Complete database design with tables and relationships
- **[Post ID Flow](post-id-flow.md)** - Facebook post ID extraction and tracking system

### Additional Documentation
- **[Migration Plan](../backend/MIGRATION_PLAN.md)** - NestJS to FastAPI migration documentation
- **[Development Guide](../backend/CLAUDE.md)** - Backend development commands and workflows

## 🏗️ System Overview

The AI Slop Detection system consists of:

1. **Browser Extension** - Detects and analyzes Facebook posts in real-time
2. **FastAPI Backend** - Processes content with multiple AI detection methods
3. **PostgreSQL Database** - Stores posts, analysis results, and chat conversations
4. **Google Gemini Integration** - Powers intelligent chat about detection results

## 🔗 Key Components

### Detection Capabilities
- **Text Analysis** - Pattern-based AI detection for text content
- **Image Analysis** - ClipBased models for AI-generated image detection  
- **Video Analysis** - SlowFast models for temporal video analysis

### User Interaction
- **Real-time Detection** - Instant analysis as users browse Facebook
- **AI Chat** - Context-aware conversations about detection results
- **Analytics Tracking** - Comprehensive user behavior and interaction metrics

### Data Management
- **Post Deduplication** - Consistent Facebook post ID tracking
- **Result Caching** - Efficient storage and retrieval of analysis results
- **Chat History** - Persistent conversations linked to specific posts

## 📖 Documentation Standards

All documentation in this directory follows these standards:

- **Clear Structure** - Hierarchical organization with table of contents
- **Code Examples** - Practical examples with syntax highlighting
- **Architecture Diagrams** - Visual representations where helpful
- **API Documentation** - Complete request/response examples
- **Cross-References** - Links between related documentation

## 🔄 Keeping Documentation Updated

When making system changes:

1. **Update affected documentation** in this directory
2. **Add new documentation** for new features or components
3. **Update cross-references** in related documentation
4. **Verify code examples** still work with current implementation

## 🤝 Contributing

When adding new documentation:

1. Place files in this `docs/` directory
2. Use descriptive filenames with kebab-case (e.g., `new-feature-guide.md`)
3. Add entry to this README.md
4. Follow existing formatting and structure conventions
5. Include practical examples and code snippets