import { ChatPage } from "@/features/chat/components/chat-page";

type ConversationRouteProps = {
  params: Promise<{ conversationId: string }>;
};

export default async function ConversationRoute({
  params,
}: ConversationRouteProps) {
  const { conversationId } = await params;

  return <ChatPage conversationId={conversationId} />;
}
