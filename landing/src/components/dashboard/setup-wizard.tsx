"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Loader2, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { postApi, getApi } from "@/lib/dashboard-api";

interface SetupState {
  instagram_connected: boolean;
  instagram_username?: string | null;
  gdrive_connected: boolean;
  gdrive_email?: string | null;
  media_folder_configured: boolean;
  media_indexed: boolean;
  media_count: number;
  posts_per_day: number;
  posting_hours_start: number;
  posting_hours_end: number;
  schedule_configured?: boolean;
  onboarding_completed: boolean;
}

interface SetupWizardProps {
  initialState: SetupState;
}

const STEPS = [
  { title: "Connect Instagram", description: "Link your Instagram account for automated posting." },
  { title: "Connect Google Drive", description: "Link Google Drive to access your media library." },
  { title: "Configure Media Folder", description: "Point to the Google Drive folder containing your media." },
  { title: "Index Media", description: "Scan and categorize your media files." },
  { title: "Set Schedule", description: "Configure how often and when to post." },
  { title: "Complete", description: "Review your setup and start posting." },
];

const hourOptions = Array.from({ length: 24 }, (_, i) => ({
  value: String(i),
  label: `${i === 0 ? "12" : i > 12 ? String(i - 12) : String(i)}:00 ${i < 12 ? "AM" : "PM"}`,
}));

export function SetupWizard({ initialState }: SetupWizardProps) {
  const router = useRouter();
  const [state, setState] = useState<SetupState>(initialState);
  const [step, setStep] = useState(() => inferStep(initialState));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [folderUrl, setFolderUrl] = useState("");
  const [folderResult, setFolderResult] = useState<{ file_count: number; categories: string[] } | null>(null);
  const [indexResult, setIndexResult] = useState<{ new: number; updated: number; errors: number } | null>(null);
  const [postsPerDay, setPostsPerDay] = useState<number>(state.posts_per_day);
  const [hoursStart, setHoursStart] = useState(String(state.posting_hours_start));
  const [hoursEnd, setHoursEnd] = useState(String(state.posting_hours_end));
  const [scheduleSaved, setScheduleSaved] = useState(
    initialState.schedule_configured === true && initialState.onboarding_completed
  );

  async function refreshState() {
    setError(null);
    try {
      const data = await postApi("init");
      if (data?.setup_state) {
        setState(data.setup_state);
        if (data.setup_state.schedule_configured && data.setup_state.onboarding_completed) {
          setScheduleSaved(true);
        }
      }
      return data?.setup_state as SetupState | undefined;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
      return undefined;
    }
  }

  async function handleOAuth(provider: "instagram" | "google-drive") {
    setError(null);
    setLoading(true);
    try {
      const data = await getApi(`oauth-url/${provider}`);
      if (data?.auth_url) window.open(data.auth_url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefreshConnection() {
    setLoading(true);
    try {
      await refreshState();
    } finally {
      setLoading(false);
    }
  }

  async function handleConfigureFolder() {
    setError(null);
    setLoading(true);
    try {
      const data = await postApi("media-folder", { folder_url: folderUrl });
      setFolderResult(data);
      await refreshState();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleStartIndexing() {
    setError(null);
    setLoading(true);
    try {
      const data = await postApi("start-indexing");
      setIndexResult(data);
      await refreshState();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveSchedule() {
    setError(null);
    setLoading(true);
    try {
      await postApi("schedule", {
        posts_per_day: postsPerDay,
        posting_hours_start: Number(hoursStart),
        posting_hours_end: Number(hoursEnd),
      });
      setState((prev) => ({
        ...prev,
        posts_per_day: postsPerDay,
        posting_hours_start: Number(hoursStart),
        posting_hours_end: Number(hoursEnd),
        schedule_configured: true,
      }));
      setScheduleSaved(true);
      setStep(5);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleComplete() {
    setError(null);
    setLoading(true);
    try {
      await postApi("complete");
      router.push("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setLoading(false);
    }
  }

  function canAdvance(): boolean {
    switch (step) {
      case 0: return state.instagram_connected;
      case 1: return state.gdrive_connected;
      case 2: return state.media_folder_configured;
      case 3: return state.media_indexed;
      case 4: return scheduleSaved;
      case 5: return true;
      default: return false;
    }
  }

  function isStepComplete(s: number): boolean {
    switch (s) {
      case 0: return state.instagram_connected;
      case 1: return state.gdrive_connected;
      case 2: return state.media_folder_configured;
      case 3: return state.media_indexed;
      case 4: return scheduleSaved;
      case 5: return state.onboarding_completed;
      default: return false;
    }
  }

  const isSkippable = step === 1;
  const progress = ((step + 1) / STEPS.length) * 100;
  const currentStep = STEPS[step];

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>Step {step + 1} of {STEPS.length}</span>
          <span>{Math.round(progress)}%</span>
        </div>
        <Progress value={progress} />
        <div className="flex gap-1.5">
          {STEPS.map((_, i) => (
            <button
              key={i}
              onClick={() => i <= step && setStep(i)}
              disabled={i > step}
              className={`flex h-6 w-6 items-center justify-center rounded-full text-xs transition-colors ${
                isStepComplete(i)
                  ? "bg-green-500/15 text-green-600"
                  : i === step
                    ? "bg-primary text-primary-foreground"
                    : i < step
                      ? "bg-muted text-muted-foreground cursor-pointer"
                      : "bg-muted text-muted-foreground opacity-50"
              }`}
            >
              {isStepComplete(i) ? <CheckCircle2 className="size-4" /> : i + 1}
            </button>
          ))}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{currentStep.title}</CardTitle>
          <CardDescription>{currentStep.description}</CardDescription>
        </CardHeader>

        <CardContent>
          {error && (
            <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800 flex items-center justify-between">
              <span>{error}</span>
              <button onClick={() => setError(null)} className="ml-2 text-red-600 hover:text-red-800 font-medium">Dismiss</button>
            </div>
          )}

          {step === 0 && (
            <OAuthStep
              label="Instagram"
              connected={state.instagram_connected}
              username={state.instagram_username}
              loading={loading}
              onConnect={() => handleOAuth("instagram")}
              onRefresh={handleRefreshConnection}
            />
          )}

          {step === 1 && (
            <OAuthStep
              label="Google Drive"
              connected={state.gdrive_connected}
              username={state.gdrive_email}
              loading={loading}
              onConnect={() => handleOAuth("google-drive")}
              onRefresh={handleRefreshConnection}
            />
          )}

          {step === 2 && (
            <div className="space-y-4">
              {state.media_folder_configured && !folderResult && (
                <div className="flex items-center gap-2">
                  <Badge className="bg-green-500/15 text-green-600 border-green-500/25">Configured</Badge>
                  <span className="text-sm text-muted-foreground">{state.media_count} files</span>
                </div>
              )}
              <div className="space-y-2">
                <Label htmlFor="folder-url">Google Drive Folder URL</Label>
                <Input
                  id="folder-url"
                  placeholder="https://drive.google.com/drive/folders/..."
                  value={folderUrl}
                  onChange={(e) => setFolderUrl(e.target.value)}
                />
              </div>
              <Button
                onClick={handleConfigureFolder}
                disabled={loading || !/^https:\/\/drive\.google\.com\/drive\/folders\/[a-zA-Z0-9_-]+/.test(folderUrl)}
              >
                {loading ? <Loader2 className="size-4 animate-spin" /> : null}
                Configure Folder
              </Button>
              {folderResult && (
                <div className="rounded-md border p-3 text-sm space-y-1">
                  <p><span className="font-medium">{folderResult.file_count}</span> files found</p>
                  {folderResult.categories.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {folderResult.categories.map((cat) => (
                        <Badge key={cat} variant="outline">{cat}</Badge>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              {state.media_indexed && !indexResult && (
                <div className="flex items-center gap-2">
                  <Badge className="bg-green-500/15 text-green-600 border-green-500/25">Indexed</Badge>
                  <span className="text-sm text-muted-foreground">{state.media_count} files</span>
                </div>
              )}
              <Button onClick={handleStartIndexing} disabled={loading}>
                {loading ? <Loader2 className="size-4 animate-spin" /> : null}
                {state.media_indexed ? "Re-index Media" : "Start Indexing"}
              </Button>
              {indexResult && (
                <div className="rounded-md border p-3 text-sm space-y-1">
                  <p><span className="font-medium">{indexResult.new}</span> new files indexed</p>
                  <p><span className="font-medium">{indexResult.updated}</span> files updated</p>
                  {indexResult.errors > 0 && (
                    <p className="text-destructive"><span className="font-medium">{indexResult.errors}</span> errors</p>
                  )}
                </div>
              )}
            </div>
          )}

          {step === 4 && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="posts-per-day">Posts per day</Label>
                <Input
                  id="posts-per-day"
                  type="number"
                  min={1}
                  max={50}
                  value={postsPerDay}
                  onChange={(e) => setPostsPerDay(parseInt(e.target.value, 10) || 0)}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Start hour</Label>
                  <Select value={hoursStart} onValueChange={setHoursStart}>
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {hourOptions.map((h) => (
                        <SelectItem key={h.value} value={h.value}>{h.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>End hour</Label>
                  <Select value={hoursEnd} onValueChange={setHoursEnd}>
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {hourOptions.map((h) => (
                        <SelectItem key={h.value} value={h.value}>{h.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <Button onClick={handleSaveSchedule} disabled={loading || postsPerDay < 1}>
                {loading ? <Loader2 className="size-4 animate-spin" /> : null}
                Save Schedule
              </Button>
            </div>
          )}

          {step === 5 && (
            <div className="space-y-3">
              <SummaryRow label="Instagram" connected={state.instagram_connected} />
              <SummaryRow label="Google Drive" connected={state.gdrive_connected} />
              <SummaryRow label="Media folder" connected={state.media_folder_configured} detail={state.media_folder_configured ? `${state.media_count} files` : undefined} />
              <SummaryRow label="Media indexed" connected={state.media_indexed} />
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">Schedule</span>
                <span className="text-muted-foreground">
                  {state.posts_per_day} posts/day, {formatHour(state.posting_hours_start)}&ndash;{formatHour(state.posting_hours_end)}
                </span>
              </div>
            </div>
          )}
        </CardContent>

        <CardFooter className="justify-between">
          <Button
            variant="outline"
            onClick={() => setStep((s) => s - 1)}
            disabled={step === 0}
          >
            Back
          </Button>
          <div className="flex gap-2">
            {isSkippable && !canAdvance() && (
              <Button variant="ghost" onClick={() => setStep((s) => s + 1)}>
                Skip
              </Button>
            )}
            {step < 5 ? (
              <Button
                onClick={() => setStep((s) => s + 1)}
                disabled={!canAdvance()}
              >
                Next
              </Button>
            ) : (
              <Button onClick={handleComplete} disabled={loading || !state.instagram_connected}>
                {loading ? <Loader2 className="size-4 animate-spin" /> : null}
                Complete Setup
              </Button>
            )}
          </div>
        </CardFooter>
      </Card>
    </div>
  );
}

function OAuthStep({
  label,
  connected,
  username,
  loading,
  onConnect,
  onRefresh,
}: {
  label: string;
  connected: boolean;
  username?: string | null;
  loading: boolean;
  onConnect: () => void;
  onRefresh: () => void;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium">Status:</span>
        {connected ? (
          <>
            <Badge className="bg-green-500/15 text-green-600 border-green-500/25">Connected</Badge>
            {username && <span className="text-sm text-muted-foreground">{username}</span>}
          </>
        ) : (
          <Badge variant="secondary">Not connected</Badge>
        )}
      </div>
      {/* TODO: Add polling (setInterval + refreshState every 3s, capped at 60s) to auto-detect OAuth completion */}
      {!connected && (
        <div className="flex gap-2">
          <Button onClick={onConnect} disabled={loading}>
            {loading ? <Loader2 className="size-4 animate-spin" /> : <ExternalLink className="size-4" />}
            Connect {label}
          </Button>
          <Button variant="outline" onClick={onRefresh} disabled={loading}>
            {loading ? <Loader2 className="size-4 animate-spin" /> : null}
            Refresh
          </Button>
        </div>
      )}
    </div>
  );
}

function SummaryRow({ label, connected, detail }: { label: string; connected: boolean; detail?: string }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="font-medium">{label}</span>
      <div className="flex items-center gap-2">
        {detail && <span className="text-muted-foreground">{detail}</span>}
        {connected ? (
          <Badge className="bg-green-500/15 text-green-600 border-green-500/25">Done</Badge>
        ) : (
          <Badge variant="secondary">Pending</Badge>
        )}
      </div>
    </div>
  );
}

function formatHour(h: number): string {
  if (h === 0) return "12 AM";
  if (h === 12) return "12 PM";
  return h > 12 ? `${h - 12} PM` : `${h} AM`;
}

function inferStep(state: SetupState): number {
  if (!state.instagram_connected) return 0;
  if (!state.gdrive_connected) return 1;
  if (!state.media_folder_configured) return 2;
  if (!state.media_indexed) return 3;
  if (!state.onboarding_completed) return 4;
  return 5;
}
