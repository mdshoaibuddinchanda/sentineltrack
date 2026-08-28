import React, { useState } from "react";
import { Modal } from "../common/Modal";
import { TargetCreateRequest, TargetPriority } from "../../types/api";
import { Shield, AlertCircle } from "lucide-react";

interface AddTargetModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: TargetCreateRequest) => Promise<any>;
}

export function AddTargetModal({ isOpen, onClose, onSubmit }: AddTargetModalProps) {
  const [registration, setRegistration] = useState("");
  const [priority, setPriority] = useState<TargetPriority>("CRITICAL");
  const [notes, setNotes] = useState("");
  const [caseId, setCaseId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const normalizedPreview = registration.trim().toUpperCase().replace(/\s+/g, "");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!normalizedPreview || normalizedPreview.length < 4) {
      setError("Registration must be at least 4 characters long.");
      return;
    }

    try {
      setIsSubmitting(true);
      setError(null);
      await onSubmit({
        registration: normalizedPreview,
        priority,
        notes: notes.trim() || undefined,
        metadata: caseId.trim() ? { case_id: caseId.trim() } : {},
      });
      setRegistration("");
      setNotes("");
      setCaseId("");
      onClose();
    } catch (err: any) {
      setError(err?.message || "Failed to add target to watchlist.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center gap-2 font-mono">
          <Shield className="w-4 h-4 text-accent-blue" />
          <span>REGISTER TARGET TO WATCHLIST</span>
        </div>
      }
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-1.5 bg-police-750 hover:bg-police-700 rounded text-xs font-semibold text-slate-300 transition-colors font-mono"
          >
            CANCEL
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isSubmitting || !normalizedPreview}
            className="px-4 py-1.5 bg-accent-blue hover:bg-blue-600 disabled:bg-police-750 disabled:text-slate-500 rounded text-xs font-semibold text-white transition-colors font-mono"
          >
            {isSubmitting ? "SAVING..." : "REGISTER TARGET"}
          </button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4 text-xs font-mono">
        {error && (
          <div className="p-3 bg-rose-950/80 border border-rose-700 rounded text-rose-200 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div>
          <label className="block text-slate-300 font-semibold mb-1">Vehicle License Plate *</label>
          <input
            type="text"
            required
            value={registration}
            onChange={(e) => setRegistration(e.target.value.toUpperCase())}
            placeholder="e.g. GJ 01 AB 1234"
            className="w-full bg-police-900 border border-police-700 focus:border-accent-blue rounded p-2.5 text-sm text-white font-mono placeholder:text-slate-600 focus:outline-none"
          />
          {normalizedPreview && (
            <div className="text-[11px] text-slate-400 mt-1">
              Normalized: <span className="text-cyan-300 font-bold">{normalizedPreview}</span>
            </div>
          )}
        </div>

        <div>
          <label className="block text-slate-300 font-semibold mb-1">Alert Priority *</label>
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as TargetPriority)}
            className="w-full bg-police-900 border border-police-700 focus:border-accent-blue rounded p-2 text-slate-200 font-mono focus:outline-none"
          >
            <option value="CRITICAL">CRITICAL (Immediate High-Urgency Broadcast)</option>
            <option value="HIGH">HIGH (Investigation Priority)</option>
            <option value="NORMAL">NORMAL (Standard Monitoring)</option>
            <option value="LOW">LOW (Passive Log Only)</option>
          </select>
        </div>

        <div>
          <label className="block text-slate-300 font-semibold mb-1">Case / FIR Reference ID</label>
          <input
            type="text"
            value={caseId}
            onChange={(e) => setCaseId(e.target.value)}
            placeholder="e.g. FIR-2026-904"
            className="w-full bg-police-900 border border-police-700 focus:border-accent-blue rounded p-2 text-slate-200 font-mono placeholder:text-slate-600 focus:outline-none"
          />
        </div>

        <div>
          <label className="block text-slate-300 font-semibold mb-1">Investigation Notes</label>
          <textarea
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Reason for surveillance, suspect details, or vehicle description..."
            className="w-full bg-police-900 border border-police-700 focus:border-accent-blue rounded p-2 text-slate-200 font-mono placeholder:text-slate-600 focus:outline-none"
          />
        </div>
      </form>
    </Modal>
  );
}
