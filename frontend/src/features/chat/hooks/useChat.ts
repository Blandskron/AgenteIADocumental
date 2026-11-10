import type {
  Conversation,
  Message,
} from "@/entities/conversation/model/types.ts";
import type { DocumentItem } from "@/entities/document/model/types.ts";
import type { TransferJournal } from "@/features/transfers/tracked-transfer.ts";
import type { MaybeClient } from "@/shared/api/types.ts";
import { toError } from "@/shared/lib/errors.ts";
import { useState } from "react";
interface ChatOptions {
  chatClient: MaybeClient;
  documentClient: MaybeClient;
  activeConversation: Conversation;
  addMessage: (message: Message) => void;
  setSelectedDocuments: (documents: DocumentItem[]) => void;
  selectedFile: File | null;
  clearSelectedFile: () => void;
  transfers: TransferJournal;
}

import {
  createAssistantMessage,
  createUserMessage,
} from "@/entities/message/model/message.factory";
import { askExistingDocuments } from "@/features/chat/api/chat.api";
import { useDocumentQuestionFlow } from "./useDocumentQuestionFlow";

function assistantErrorMessage(
  error: { message?: string },
  action = "completar la solicitud",
) {
  const reason = error?.message ? ` ${error.message}` : "";
  return `Lo siento, ahora no puedo ${action}.${reason} Revisa la configuracion del proveedor de IA y vuelve a intentarlo.`;
}

export function useChat({
  chatClient,
  documentClient,
  activeConversation,
  addMessage,
  setSelectedDocuments,
  selectedFile,
  clearSelectedFile,
  transfers,
}: ChatOptions) {
  const [question, setQuestion] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const documentQuestionFlow = useDocumentQuestionFlow({
    documentClient,
    conversationId: activeConversation?.id,
    clearSelectedFile,
    transfers,
  });

  function selectedDocumentIds(extraDocuments: DocumentItem[] = []) {
    const ids = [
      ...(activeConversation?.selectedDocuments || []).map(
        (document) => document.documentId,
      ),
      ...extraDocuments.map((document) => document.documentId),
    ];
    return [...new Set(ids.filter(Boolean))];
  }

  function attachDocumentsToConversation(documents: DocumentItem[]) {
    if (!documents.length || !setSelectedDocuments) return;
    setSelectedDocuments([
      ...(activeConversation?.selectedDocuments || []),
      ...documents,
    ]);
  }

  async function askExisting(
    cleanQuestion: string,
    extraDocuments: DocumentItem[] = [],
  ) {
    if (!activeConversation?.id) return;
    const payload = await askExistingDocuments(chatClient, {
      question: cleanQuestion,
      sessionId: activeConversation.id,
      documentIds: selectedDocumentIds(extraDocuments),
    });

    addMessage(createAssistantMessage(payload.answer, payload.sources || []));
  }

  async function uploadAndAsk(cleanQuestion: string) {
    const document = await documentQuestionFlow.uploadAndWait(selectedFile!);
    attachDocumentsToConversation([document]);
    await askExisting(cleanQuestion, [document]);
  }

  async function uploadOnly() {
    if (!selectedFile || isBusy) return;

    setIsBusy(true);

    try {
      const document = await documentQuestionFlow.uploadAndWait(selectedFile!);
      attachDocumentsToConversation([document]);
      addMessage(
        createAssistantMessage(
          `Documento procesado: ${document.filename}. Ya puedes preguntarme sobre su contenido.`,
        ),
      );
    } catch (caughtError) {
      const error = toError(caughtError);
      addMessage(
        createAssistantMessage(
          assistantErrorMessage(error, "procesar el documento"),
        ),
      );
    } finally {
      setIsBusy(false);
    }
  }

  async function submit() {
    const cleanQuestion = question.trim();
    if (!cleanQuestion || isBusy) return;

    const userText = selectedFile
      ? `${cleanQuestion}\n\nAdjunto: ${selectedFile.name}`
      : cleanQuestion;
    setQuestion("");
    addMessage(createUserMessage(userText));
    setIsBusy(true);

    try {
      if (selectedFile) {
        await uploadAndAsk(cleanQuestion);
      } else {
        await askExisting(cleanQuestion);
      }
    } catch (caughtError) {
      const error = toError(caughtError);
      addMessage(createAssistantMessage(assistantErrorMessage(error)));
    } finally {
      setIsBusy(false);
    }
  }

  function resetComposer() {
    setQuestion("");
    clearSelectedFile();
  }

  return {
    question,
    setQuestion,
    isBusy,
    submit,
    uploadOnly,
    resetComposer,
  };
}
