/**
 * Admin document upload page / modal wrapper.
 * Owner: P7
 *
 * Shows a file picker (PDF only), department and doc_type text inputs,
 * and a status indicator that polls GET /documents/{document_id}/status
 * until ingestion_status reaches "done" or "failed".
 *
 * Only rendered for users with role === "admin"; non-admins are redirected
 * to the chat page.
 */
import React from "react";
import UploadModal from "./UploadModal";

interface UploadPageProps {
  onNavigateBack?: () => void;
}

export const UploadPage: React.FC<UploadPageProps> = ({ onNavigateBack }) => {
  const handleBack = () => {
    if (onNavigateBack) {
      onNavigateBack();
    } else {
      window.history.pushState({}, "", "/chat");
      window.dispatchEvent(new PopStateEvent("popstate"));
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-canvas p-4 font-sans text-ink">
      <UploadModal
        isOpen={true}
        onClose={handleBack}
        onUploadSuccess={() => {
          // Optional callback on success
        }}
      />
    </div>
  );
};

export default UploadPage;