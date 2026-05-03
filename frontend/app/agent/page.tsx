"use client";

import { useState, useEffect } from "react";
import { Bot, MessageSquare, Brain, Save, Loader2, Trash2, Send, Check } from "lucide-react";
import { agentAPI, AgentConfig } from "@/lib/api";


export default function AgentPage() {
  return (
    <main className="min-h-screen bg-white px-6 py-12">
      <div className="mx-auto max-w-4xl">
        <AgentSettings />
      </div>
    </main>
  );
}

function AgentSettings() {
  const [config, setConfig] = useState<AgentConfig | null>(null);
  const [systemPrompt, setSystemPrompt] = useState("");
  const [personalityPrompt, setPersonalityPrompt] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Test state
  const [testQuestion, setTestQuestion] = useState("");
  const [testAnswer, setTestAnswer] = useState<{ answer: string; sources: string[] } | null>(null);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const data = await agentAPI.getConfig();
      setConfig(data);
      if (data) {
        setSystemPrompt(data.system_prompt || "");
        setPersonalityPrompt(data.personality_prompt || "");
      }
    } catch (error) {
      console.error("Failed to load config:", error);
    } finally {
      setLoading(false);
    }
  };

  const saveConfig = async () => {
    setSaving(true);
    setMessage(null);
    try {
      await agentAPI.saveConfig(systemPrompt, personalityPrompt);
      setMessage({ type: "success", text: "Configuration saved successfully!" });
      loadConfig();
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : "Failed to save";
      setMessage({ type: "error", text: msg });
    } finally {
      setSaving(false);
      setTimeout(() => setMessage(null), 4000);
    }
  };

  const deleteConfig = async () => {
    if (!confirm("Are you sure you want to delete the agent configuration?")) return;
    try {
      await agentAPI.deleteConfig();
      setConfig(null);
      setSystemPrompt("");
      setPersonalityPrompt("");
      setMessage({ type: "success", text: "Configuration deleted." });
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : "Failed to delete";
      setMessage({ type: "error", text: msg });
    }
  };

  const testAgent = async () => {
    if (!testQuestion.trim()) return;
    setTesting(true);
    setTestAnswer(null);
    try {
      const result = await agentAPI.test(testQuestion);
      setTestAnswer(result);
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : "Test failed";
      setMessage({ type: "error", text: msg });
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <header className="border-b border-black pb-6">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center border-2 border-black bg-black text-white">
            <Bot className="h-6 w-6" />
          </div>
          <div>
            <h1 className="font-mono text-3xl font-black tracking-tight uppercase">Agent Configuration</h1>
            <p className="font-mono text-xs uppercase tracking-widest text-zinc-500">
              Configure your AI agent's behavior and personality
            </p>
          </div>
        </div>
      </header>

      {/* Status Banner */}
      {config ? (
        <div className="flex items-center gap-3 border border-green-500 bg-green-50 px-4 py-3">
          <Check className="h-4 w-4 text-green-600" />
          <span className="font-mono text-xs font-bold uppercase tracking-widest text-green-700">
            Agent Configured
          </span>
        </div>
      ) : (
        <div className="flex items-center gap-3 border border-zinc-300 bg-zinc-50 px-4 py-3">
          <Bot className="h-4 w-4 text-zinc-400" />
          <span className="font-mono text-xs font-bold uppercase tracking-widest text-zinc-500">
            No Configuration - Create one below
          </span>
        </div>
      )}

      {/* Message */}
      {message && (
        <div className={`border px-4 py-3 ${message.type === "success" ? "border-green-500 bg-green-50" : "border-red-500 bg-red-50"}`}>
          <p className="font-mono text-xs font-bold uppercase tracking-widest">
            {message.text}
          </p>
        </div>
      )}

      {/* System Prompt */}
      <div className="space-y-3">
        <label className="flex items-center gap-2 text-xs font-black uppercase tracking-widest">
          <Brain className="h-4 w-4" />
          System Prompt
        </label>
        <p className="text-[10px] text-zinc-500">
          Defines the agent's role, behavior, and response guidelines. This is used as the foundation for all AI responses.
        </p>
        <textarea
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
          placeholder="You are a helpful hotel concierge named Inika. You assist guests with their needs..."
          rows={8}
          className="input-field resize-none"
        />
      </div>

      {/* Personality Prompt */}
      <div className="space-y-3">
        <label className="flex items-center gap-2 text-xs font-black uppercase tracking-widest">
          <MessageSquare className="h-4 w-4" />
          Personality Prompt
        </label>
        <p className="text-[10px] text-zinc-500">
          Defines the agent's tone, communication style, and personality traits.
        </p>
        <textarea
          value={personalityPrompt}
          onChange={(e) => setPersonalityPrompt(e.target.value)}
          placeholder="You are friendly, professional, and always polite. You use the guest's name naturally..."
          rows={6}
          className="input-field resize-none"
        />
      </div>

      {/* Action Buttons */}
      <div className="flex gap-4">
        <button
          onClick={saveConfig}
          disabled={saving}
          className="flex flex-1 items-center justify-center gap-2 border border-black bg-black px-6 py-4 font-mono text-xs font-black uppercase tracking-widest text-white transition hover:bg-zinc-800 disabled:opacity-50"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          {saving ? "Saving..." : "Save Configuration"}
        </button>
        {config && (
          <button
            onClick={deleteConfig}
            className="flex items-center justify-center gap-2 border border-red-300 px-6 py-4 font-mono text-xs font-black uppercase tracking-widest text-red-600 transition hover:bg-red-50"
          >
            <Trash2 className="h-4 w-4" />
            Delete
          </button>
        )}
      </div>

      {/* Test Section */}
      <div className="border-t border-zinc-200 pt-8">
        <h2 className="mb-4 text-sm font-black uppercase tracking-widest text-zinc-500">
          Test Agent
        </h2>

        <div className="flex gap-3">
          <input
            type="text"
            value={testQuestion}
            onChange={(e) => setTestQuestion(e.target.value)}
            placeholder="Ask the agent a question..."
            className="input-field flex-1"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !testing) {
                testAgent();
              }
            }}
          />
          <button
            onClick={testAgent}
            disabled={testing || !testQuestion.trim()}
            className="flex items-center gap-2 border border-black bg-black px-6 py-3 font-mono text-xs font-black uppercase tracking-widest text-white transition hover:bg-zinc-800 disabled:opacity-50"
          >
            {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            Test
          </button>
        </div>

        {testAnswer && (
          <div className="mt-4 border border-black/20 bg-zinc-50 p-6">
            <p className="mb-3 text-[10px] font-black uppercase tracking-widest text-zinc-500">
              Response
            </p>
            <p className="font-mono text-sm leading-relaxed">{testAnswer.answer}</p>
            {testAnswer.sources.length > 0 && (
              <div className="mt-4 border-t border-zinc-200 pt-4">
                <p className="text-[10px] font-black uppercase tracking-widest text-zinc-500">
                  Sources
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {testAnswer.sources.map((source, i) => (
                    <span key={i} className="badge">{source}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-black pt-6">
        <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-widest text-zinc-400">
          <span>Agent Configuration v1.0</span>
          <span>Inika Bot</span>
        </div>
      </div>
    </div>
  );
}