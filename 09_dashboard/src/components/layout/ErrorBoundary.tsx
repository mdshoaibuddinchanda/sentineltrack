import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error caught by ErrorBoundary:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="p-6 bg-police-850 border border-rose-900/60 rounded-lg text-slate-200 m-4 flex flex-col items-center justify-center text-center space-y-3">
          <AlertTriangle className="w-8 h-8 text-rose-500" />
          <h3 className="text-base font-semibold text-rose-300">
            {this.props.fallbackTitle || "Component Render Error"}
          </h3>
          <p className="text-xs text-slate-400 max-w-md font-mono">
            {this.state.error?.message || "An unexpected error occurred in this view component."}
          </p>
          <p className="text-xs text-slate-500 max-w-md text-center">
            You can select another page from the navigation above. This page resets automatically when you change tabs.
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-police-700 hover:bg-police-600 rounded text-xs font-semibold text-white transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Try this page again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
