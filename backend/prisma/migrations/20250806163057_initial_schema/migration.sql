-- CreateTable
CREATE TABLE "post" (
    "id" TEXT NOT NULL,
    "postId" TEXT NOT NULL,
    "content" TEXT NOT NULL,
    "author" TEXT,
    "verdict" TEXT NOT NULL,
    "confidence" DOUBLE PRECISION NOT NULL,
    "explanation" TEXT,
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "post_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "chat" (
    "id" TEXT NOT NULL,
    "postDbId" TEXT NOT NULL,
    "role" TEXT NOT NULL,
    "message" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "chat_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "post_postId_key" ON "post"("postId");

-- AddForeignKey
ALTER TABLE "chat" ADD CONSTRAINT "chat_postDbId_fkey" FOREIGN KEY ("postDbId") REFERENCES "post"("id") ON DELETE CASCADE ON UPDATE CASCADE;
