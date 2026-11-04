import { useState } from "react";

import { createAssistantMessage, createUserMessage } from "../../../entities/message/model/message.factory";
import { askExistingDocuments } from "../api/chat.api";
import { useDocumentQuestionFlow } from "./useDocumentQuestionFlow";

function assistantErrorMessage(error, action = "completar la solicitud") {
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
}) {
  const [question, setQuestion] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const documentQuestionFlow = useDocumentQuestionFlow({
    documentClient,
    conversationId: activeConversation?.id,
    clearSelectedFile,
    transfers,
  });

  function selectedDocumentIds(extraDocuments = []) {
    const ids = [
      ...(activeConversation?.selectedDocuments || []).map((document) => document.documentId),
      ...extraDocuments.map((document) => document.documentId),
    ];
    return [...new Set(ids.filter(Boolean))];
  }

  function attachDocumentsToConversation(documents) {
    if (!documents.length || !setSelectedDocuments) return;
    setSelectedDocuments([...(activeConversation?.selectedDocuments || []), ...documents]);
  }

  async function askExisting(cleanQuestion, extraDocuments = []) {
    if (!activeConversation?.id) return;
    const payload = await askExistingDocuments(chatClient, {
      question: cleanQuestion,
      sessionId: activeConversation.id,
      documentIds: selectedDocumentIds(extraDocuments),
    });

    addMessage(createAssistantMessage(payload.answer, payload.sources || []));
  }

  async function uploadAndAsk(cleanQuestion) {
    const document = await documentQuestionFlow.uploadAndWait(selectedFile);
    attachDocumentsToConversation([document]);
    await askExisting(cleanQuestion, [document]);
  }

  async function uploadOnly() {
    if (!selectedFile || isBusy) return;

    setIsBusy(true);

    try {
      const document = await documentQuestionFlow.uploadAndWait(selectedFile);
      attachDocumentsToConversation([document]);
      addMessage(createAssistantMessage(`Documento procesado: ${document.filename}. Ya puedes preguntarme sobre su contenido.`));
    } catch (error) {
      addMessage(createAssistantMessage(assistantErrorMessage(error, "procesar el documento")));
    } finally {
      setIsBusy(false);
    }
  }

  async function submit() {
    const cleanQuestion = question.trim();
    if (!cleanQuestion || isBusy) return;

    const userText = selectedFile ? `${cleanQuestion}\n\nAdjunto: ${selectedFile.name}` : cleanQuestion;
    setQuestion("");
    addMessage(createUserMessage(userText));
    setIsBusy(true);

    try {
      if (selectedFile) {
        await uploadAndAsk(cleanQuestion);
      } else {
        await askExisting(cleanQuestion);
      }
    } catch (error) {
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
