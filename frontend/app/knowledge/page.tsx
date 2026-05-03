"use client";

import { useEffect, useState } from "react";
import {
  Brain,
  FileText,
  Search,
  Upload,
  Sparkles,
  Loader2,
  BookOpen,
  Database,
  RefreshCw,
  Plus,
  X,
  ChevronRight,
  MessageSquare,
} from "lucide-react";
import { wikiAPI, WikiSource, WikiPage } from "@/lib/api";


type WikiStats = {
  total_sources: number;
  total_pages: number;
  total_vectors: number;
};

export default function KnowledgePage() {
  return (
    <div className="min-h-screen overflow-x-hidden bg-white">
      <KnowledgeContent />
    </div>
  );
}

function KnowledgeContent() {
  const [activeTab, setActiveTab] = useState<"browse" | "ingest" | "query">("browse");
  const [stats, setStats] = useState<WikiStats | null>(null);
  const [sources, setSources] = useState<WikiSource[]>([]);
  const [pages, setPages] = useState<WikiPage[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<WikiPage[]>([]);
  const [loading, setLoading] = useState(true);
  const [ingesting, setIngesting] = useState(false);
  const [queryQuestion, setQueryQuestion] = useState("");
  const [queryAnswer, setQueryAnswer] = useState<string | null>(null);
  const [queryLoading, setQueryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Ingest form state
  const [ingestTitle, setIngestTitle] = useState("");
  const [ingestContent, setIngestContent] = useState("");
  const [ingestType, setIngestType] = useState("article");
  const [ingestTags, setIngestTags] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsData, sourcesData, pagesData] = await Promise.all([
        wikiAPI.getIndex().catch(() => null),
        wikiAPI.getSources().catch(() => ({ sources: [], total: 0 })),
        wikiAPI.getPages().catch(() => ({ pages: [], total: 0 })),
      ]);
      // Handle both old and new stats structure
      if (statsData) {
        setStats({
          total_sources: statsData.total_sources || 0,
          total_pages: statsData.total_pages || 0,
          total_vectors: 0, // Not available in new API
        });
      }
      setSources(sourcesData.sources);
      setPages(pagesData.pages);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    try {
      const results = await wikiAPI.searchPages(searchQuery);
      setSearchResults(results.pages);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Search failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleIngest = async () => {
    if (!ingestTitle.trim() || !ingestContent.trim()) {
      setError("Title and content are required");
      return;
    }
    setIngesting(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const tags = ingestTags
        .split(",")
        .map((t) => t.trim())
        .filter((t) => t);
      await wikiAPI.ingest(ingestTitle, ingestContent, ingestType, tags.length > 0 ? tags : []);
      setSuccessMsg("Source ingested successfully");
      setIngestTitle("");
      setIngestContent("");
      setIngestTags("");
      setSelectedFile(null);
      loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Ingest failed";
      setError(msg);
    } finally {
      setIngesting(false);
      setTimeout(() => setSuccessMsg(null), 4000);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      // Auto-fill title from filename
      if (!ingestTitle.trim()) {
        const nameWithoutExt = file.name.replace(/\.[^/.]+$/, "");
        setIngestTitle(nameWithoutExt.replace(/[-_]/g, " "));
      }
    }
  };

  const handleFileUpload = async () => {
    if (!selectedFile) return;

    setUploading(true);
    setError(null);
    try {
      const text = await selectedFile.text();
      const tags = ingestTags
        .split(",")
        .map((t) => t.trim())
        .filter((t) => t);

      await wikiAPI.ingest(
        ingestTitle || selectedFile.name,
        text,
        ingestType,
        tags.length > 0 ? tags : []
      );

      setSuccessMsg(`File "${selectedFile.name}" ingested successfully`);
      setIngestTitle("");
      setIngestContent("");
      setIngestTags("");
      setSelectedFile(null);
      loadData();

      // Reset file input
      const fileInput = document.getElementById("file-input") as HTMLInputElement;
      if (fileInput) fileInput.value = "";
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      setError(msg);
    } finally {
      setUploading(false);
      setTimeout(() => setSuccessMsg(null), 4000);
    }
  };

  const handleQuery = async () => {
    if (!queryQuestion.trim()) return;
    setQueryLoading(true);
    setQueryAnswer(null);
    setError(null);
    try {
      const result = await wikiAPI.query(queryQuestion);
      setQueryAnswer(result.answer);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Query failed";
      setError(msg);
    } finally {
      setQueryLoading(false);
    }
  };

  return (
    <div className="min-h-screen overflow-x-hidden bg-white px-6 py-12">
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <header className="mb-10 border-y border-black bg-white px-6 py-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center border border-black bg-black text-white">
                <Brain className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-3xl font-black tracking-tight uppercase">Knowledge Hub</h1>
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                  AI-powered RAG wiki system
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <button
                onClick={loadData}
                className="flex items-center gap-2 border border-black px-4 py-2 text-[10px] font-black uppercase tracking-[0.18em] transition hover:bg-black hover:text-white"
              >
                <RefreshCw className="h-4 w-4" />
                Refresh
              </button>
            </div>
          </div>
        </header>

        {/* Error */}
        {error && (
          <div className="mb-6 border border-red-500 bg-red-50 px-4 py-3">
            <p className="font-mono text-xs text-red-600">ERROR: {error}</p>
          </div>
        )}

        {/* Success */}
        {successMsg && (
          <div className="mb-6 border border-green-500 bg-green-50 px-4 py-3">
            <p className="font-mono text-xs text-green-700">{successMsg}</p>
          </div>
        )}

        {/* Stats */}
        {loading ? (
          <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-24 animate-pulse bg-zinc-100" />
            ))}
          </div>
        ) : (
          <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-3">
            <StatCard
              icon={Database}
              label="Total Sources"
              value={stats?.total_sources || 0}
              color="black"
            />
            <StatCard
              icon={BookOpen}
              label="Total Pages"
              value={stats?.total_pages || 0}
              color="blue"
            />
            <StatCard
              icon={Sparkles}
              label="Search Enabled"
              value={stats?.total_vectors ? "Yes" : "No"}
              color="green"
            />
          </div>
        )}

        {/* Tab Navigation */}
        <div className="mb-8 flex border-b border-black">
          <TabButton
            active={activeTab === "browse"}
            onClick={() => setActiveTab("browse")}
            icon={BookOpen}
            label="Browse"
          />
          <TabButton
            active={activeTab === "ingest"}
            onClick={() => setActiveTab("ingest")}
            icon={Upload}
            label="Ingest"
          />
          <TabButton
            active={activeTab === "query"}
            onClick={() => setActiveTab("query")}
            icon={MessageSquare}
            label="Query"
          />
        </div>

        {/* Browse Tab */}
        {activeTab === "browse" && (
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
            {/* Search */}
            <div className="border border-black">
              <div className="border-b border-black bg-black px-4 py-3">
                <h3 className="font-mono text-xs font-semibold uppercase text-white tracking-wider">
                  Search Knowledge
                </h3>
              </div>
              <div className="p-4">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                    placeholder="Search wiki pages..."
                    className="input-field flex-1"
                  />
                  <button
                    onClick={handleSearch}
                    disabled={loading || !searchQuery.trim()}
                    className="flex items-center gap-2 border border-black bg-black px-4 py-2 font-mono text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-50"
                  >
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                  </button>
                </div>

                {/* Search Results */}
                {searchResults.length > 0 ? (
                  <div className="mt-4 space-y-2">
                    {searchResults.map((page) => (
                      <div
                        key={page.id}
                        className="flex items-center justify-between border border-zinc-200 p-3 hover:bg-zinc-50"
                      >
                        <div className="flex items-center gap-3">
                          <FileText className="h-4 w-4 text-zinc-400" />
                          <span className="font-mono text-sm">{page.title}</span>
                        </div>
                        <ChevronRight className="h-4 w-4 text-zinc-400" />
                      </div>
                    ))}
                  </div>
                ) : searchQuery ? (
                  <p className="mt-4 font-mono text-sm text-zinc-500">No results found</p>
                ) : null}
              </div>
            </div>

            {/* Sources & Pages */}
            <div className="border border-black">
              <div className="border-b border-black bg-black px-4 py-3">
                <h3 className="font-mono text-xs font-semibold uppercase text-white tracking-wider">
                  Sources ({sources.length})
                </h3>
              </div>
              <div className="max-h-96 overflow-y-auto">
                {sources.length === 0 ? (
                  <div className="p-6 text-center">
                    <Database className="mx-auto mb-3 h-8 w-8 text-zinc-300" />
                    <p className="font-mono text-sm text-zinc-500">No sources yet</p>
                    <p className="font-mono text-xs text-zinc-400">Ingest content to get started</p>
                  </div>
                ) : (
                  <div className="divide-y divide-zinc-100">
                    {sources.slice(0, 10).map((source) => (
                      <div key={source.id} className="flex items-center justify-between px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="flex h-8 w-8 items-center justify-center border border-black bg-zinc-50">
                            <FileText className="h-4 w-4 text-zinc-600" />
                          </div>
                          <div>
                            <p className="font-mono text-sm font-medium">{source.title}</p>
                            <p className="font-mono text-[10px] text-zinc-500 uppercase">{source.source_type}</p>
                          </div>
                        </div>
                        <span className={`font-mono text-[10px] uppercase ${
                          source.is_processed ? "text-green-600" : "text-amber-600"
                        }`}>
                          {source.is_processed ? "processed" : "pending"}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Ingest Tab */}
        {activeTab === "ingest" && (
          <div className="border border-black">
            <div className="border-b border-black bg-black px-4 py-3">
              <h3 className="font-mono text-xs font-semibold uppercase text-white tracking-wider">
                Ingest New Content
              </h3>
            </div>
            <div className="p-6">
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                <div>
                  <label className="mb-2 block font-mono text-xs uppercase tracking-wider text-zinc-500">
                    Title
                  </label>
                  <input
                    type="text"
                    value={ingestTitle}
                    onChange={(e) => setIngestTitle(e.target.value)}
                    placeholder="Enter content title"
                    className="input-field w-full"
                  />
                </div>
                <div>
                  <label className="mb-2 block font-mono text-xs uppercase tracking-wider text-zinc-500">
                    Source Type
                  </label>
                  <select
                    value={ingestType}
                    onChange={(e) => setIngestType(e.target.value)}
                    className="input-field w-full"
                  >
                    <option value="article">Article</option>
                    <option value="paper">Paper</option>
                    <option value="book">Book</option>
                    <option value="video">Video</option>
                    <option value="podcast">Podcast</option>
                    <option value="note">Note</option>
                    <option value="webpage">Webpage</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </div>

              <div className="mt-4">
                <label className="mb-2 block font-mono text-xs uppercase tracking-wider text-zinc-500">
                  Tags (comma separated)
                </label>
                <input
                  type="text"
                  value={ingestTags}
                  onChange={(e) => setIngestTags(e.target.value)}
                  placeholder="hotel, amenities, dining"
                  className="input-field w-full"
                />
              </div>

              {/* File Upload Section */}
              <div className="mt-6 border-2 border-dashed border-zinc-300 p-6">
                <div className="flex items-center gap-3 mb-4">
                  <FileText className="h-5 w-5 text-zinc-400" />
                  <span className="font-mono text-xs uppercase tracking-wider text-zinc-600">
                    Or Upload a File
                  </span>
                </div>
                <input
                  id="file-input"
                  type="file"
                  accept=".txt,.md,.pdf,.doc,.docx,.html,.csv"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <label
                  htmlFor="file-input"
                  className="flex cursor-pointer flex-col items-center justify-center border-2 border-dashed border-black p-8 transition hover:bg-zinc-50"
                >
                  {selectedFile ? (
                    <div className="text-center">
                      <FileText className="mx-auto h-8 w-8 mb-2 text-black" />
                      <p className="font-mono text-sm font-medium">{selectedFile.name}</p>
                      <p className="font-mono text-xs text-zinc-500 mt-1">
                        {(selectedFile.size / 1024).toFixed(1)} KB
                      </p>
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          setSelectedFile(null);
                          const fileInput = document.getElementById("file-input") as HTMLInputElement;
                          if (fileInput) fileInput.value = "";
                        }}
                        className="mt-3 font-mono text-xs uppercase tracking-wider text-red-600 hover:underline"
                      >
                        Remove File
                      </button>
                    </div>
                  ) : (
                    <div className="text-center">
                      <Upload className="mx-auto h-8 w-8 text-zinc-400 mb-2" />
                      <p className="font-mono text-sm text-zinc-600">
                        Click to select a file
                      </p>
                      <p className="font-mono text-xs text-zinc-400 mt-1">
                        Supports: TXT, MD, PDF, DOC, HTML, CSV
                      </p>
                    </div>
                  )}
                </label>
                {selectedFile && (
                  <button
                    onClick={handleFileUpload}
                    disabled={uploading}
                    className="mt-4 w-full flex items-center justify-center gap-2 border border-black bg-black px-6 py-3 font-mono text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-50"
                  >
                    {uploading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Upload className="h-4 w-4" />
                    )}
                    Upload & Ingest File
                  </button>
                )}
              </div>

              <div className="mt-4">
                <div className="flex items-center gap-2 mb-2">
                  <div className="h-px flex-1 bg-zinc-200" />
                  <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-400">Or paste content below</span>
                  <div className="h-px flex-1 bg-zinc-200" />
                </div>
                <label className="mb-2 block font-mono text-xs uppercase tracking-wider text-zinc-500">
                  Content
                </label>
                <textarea
                  value={ingestContent}
                  onChange={(e) => setIngestContent(e.target.value)}
                  placeholder="Paste or type content here..."
                  rows={6}
                  className="input-field w-full font-mono text-sm"
                />
              </div>

              <div className="mt-6 flex justify-end">
                <button
                  onClick={handleIngest}
                  disabled={ingesting || !ingestTitle.trim() || !ingestContent.trim()}
                  className="flex items-center gap-2 border border-black bg-black px-6 py-3 font-mono text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-50"
                >
                  {ingesting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Upload className="h-4 w-4" />
                  )}
                  Ingest Content
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Query Tab */}
        {activeTab === "query" && (
          <div className="border border-black">
            <div className="border-b border-black bg-black px-4 py-3">
              <h3 className="font-mono text-xs font-semibold uppercase text-white tracking-wider">
                Ask the Knowledge Base
              </h3>
            </div>
            <div className="p-6">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={queryQuestion}
                  onChange={(e) => setQueryQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleQuery()}
                  placeholder="Ask a question about your knowledge base..."
                  className="input-field flex-1"
                />
                <button
                  onClick={handleQuery}
                  disabled={queryLoading || !queryQuestion.trim()}
                  className="flex items-center gap-2 border border-black bg-black px-6 py-3 font-mono text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-50"
                >
                  {queryLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="h-4 w-4" />
                  )}
                  Ask
                </button>
              </div>

              {queryAnswer && (
                <div className="mt-6">
                  <div className="border border-black bg-zinc-50 p-6">
                    <div className="mb-2 flex items-center gap-2">
                      <Brain className="h-4 w-4 text-zinc-600" />
                      <span className="font-mono text-xs uppercase tracking-wider text-zinc-500">
                        AI Response
                      </span>
                    </div>
                    <p className="font-mono text-sm leading-relaxed whitespace-pre-wrap">{queryAnswer}</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Pages List */}
        <div className="mt-8 border border-black">
          <div className="border-b border-black bg-black px-4 py-3">
            <h3 className="font-mono text-xs font-semibold uppercase text-white tracking-wider">
              Wiki Pages ({pages.length})
            </h3>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {pages.length === 0 ? (
              <div className="p-6 text-center">
                <BookOpen className="mx-auto mb-3 h-8 w-8 text-zinc-300" />
                <p className="font-mono text-sm text-zinc-500">No pages yet</p>
                <p className="font-mono text-xs text-zinc-400">Ingest sources to generate pages</p>
              </div>
            ) : (
              <div className="divide-y divide-zinc-100">
                {pages.slice(0, 20).map((page) => (
                  <div key={page.id} className="flex items-center justify-between px-4 py-4 hover:bg-zinc-50">
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 items-center justify-center border border-black bg-zinc-50">
                        <FileText className="h-4 w-4 text-zinc-600" />
                      </div>
                      <div>
                        <p className="font-mono text-sm font-medium">{page.title}</p>
                        <div className="mt-1 flex items-center gap-2">
                          <span className="font-mono text-[10px] uppercase text-zinc-400">{page.page_type}</span>
                          {page.tags && page.tags.length > 0 && (
                            <>
                              <span className="text-zinc-200">•</span>
                              <span className="font-mono text-[10px] text-zinc-400">
                                {page.tags.slice(0, 3).join(", ")}
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                    <ChevronRight className="h-4 w-4 text-zinc-400" />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <footer className="mt-16 border-t border-black bg-black px-6 py-8">
          <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500">
            <span>Knowledge Hub v1.0</span>
            <span>Inika Bot</span>
          </div>
        </footer>
      </div>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  color: string;
}) {
  const colorClasses: Record<string, string> = {
    black: "bg-black text-white",
    blue: "bg-blue-600 text-white",
    green: "bg-green-600 text-white",
  };

  return (
    <div className="border border-black p-4">
      <div className="mb-3 flex items-center gap-2">
        <Icon className="h-4 w-4 opacity-70" />
        <span className="font-mono text-xs uppercase tracking-wider opacity-70">{label}</span>
      </div>
      <div className="font-mono text-2xl font-bold">{value}</div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon: Icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 border-b-2 px-6 py-4 font-mono text-xs font-semibold uppercase tracking-wider transition ${
        active
          ? "border-black text-black"
          : "border-transparent text-zinc-400 hover:text-black"
      }`}
    >
      <Icon className="h-4 w-4" />
      {label}
    </button>
  );
}
