export function TelegramPreview() {
  return (
    <section className="py-16 md:py-24">
      <div className="mx-auto max-w-5xl px-4">
        <div className="grid items-center gap-12 md:grid-cols-2">
          {/* Left: text */}
          <div>
            <h2 className="text-3xl font-bold tracking-tight">
              Your Stories, Your Schedule, Your Approval
            </h2>
            <p className="mt-4 text-muted-foreground">
              Every scheduled story is sent to your Telegram chat for review.
              See the image, read the details, and decide with a single tap.
              Nothing posts without your say-so.
            </p>
            <ul className="mt-6 space-y-3 text-sm text-muted-foreground">
              <li className="flex items-start gap-2">
                <span className="mt-0.5 block h-1.5 w-1.5 shrink-0 rounded-full bg-foreground" />
                Preview each story before it goes live
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-0.5 block h-1.5 w-1.5 shrink-0 rounded-full bg-foreground" />
                Approve, skip, or reject with one tap
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-0.5 block h-1.5 w-1.5 shrink-0 rounded-full bg-foreground" />
                Auto-post or manual workflow — your choice
              </li>
            </ul>
          </div>

          {/* Right: Telegram-style mockup */}
          <div className="flex justify-center md:justify-end">
            <TelegramMockup />
          </div>
        </div>
      </div>
    </section>
  )
}

function TelegramMockup() {
  return (
    <div
      className="w-full max-w-xs overflow-hidden rounded-2xl shadow-xl"
      role="img"
      aria-label="Telegram chat mockup showing a story approval notification with action buttons"
    >
      {/* Header bar */}
      <div className="flex items-center gap-3 bg-[#17212b] px-4 py-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#5288c1] text-sm font-bold text-white">
          S
        </div>
        <div>
          <p className="text-sm font-medium text-white">Storydump</p>
          <p className="text-xs text-[#6c7883]">bot</p>
        </div>
      </div>

      {/* Chat body */}
      <div className="space-y-3 bg-[#0e1621] px-3 py-4">
        {/* Message bubble */}
        <div className="max-w-[85%] rounded-lg bg-[#182533] p-3">
          {/* Image placeholder */}
          <div className="flex h-40 items-center justify-center rounded bg-[#1c2e3d]">
            <div className="text-center">
              <div className="mx-auto h-10 w-10 rounded-lg bg-[#2b5278] opacity-60" />
              <p className="mt-2 text-xs text-[#6c7883]">story_photo.jpg</p>
            </div>
          </div>
          {/* Caption */}
          <div className="mt-2 space-y-1">
            <p className="text-sm text-white">
              Scheduled for 2:30 PM
            </p>
            <p className="text-xs text-[#6c7883]">
              Category: memes &middot; Posted 0 times
            </p>
          </div>
        </div>

        {/* Action buttons grid */}
        <div className="max-w-[85%] space-y-px overflow-hidden rounded-lg">
          <div className="grid grid-cols-2 gap-px">
            <button
              type="button"
              className="bg-[#182533] px-3 py-2.5 text-center text-sm font-medium text-[#5288c1] transition-colors hover:bg-[#1e3347]"
              tabIndex={-1}
              aria-hidden="true"
            >
              Post Now
            </button>
            <button
              type="button"
              className="bg-[#182533] px-3 py-2.5 text-center text-sm font-medium text-[#5288c1] transition-colors hover:bg-[#1e3347]"
              tabIndex={-1}
              aria-hidden="true"
            >
              Auto Post
            </button>
          </div>
          <div className="grid grid-cols-2 gap-px">
            <button
              type="button"
              className="bg-[#182533] px-3 py-2.5 text-center text-sm font-medium text-[#5288c1] transition-colors hover:bg-[#1e3347]"
              tabIndex={-1}
              aria-hidden="true"
            >
              Skip
            </button>
            <button
              type="button"
              className="bg-[#182533] px-3 py-2.5 text-center text-sm font-medium text-[#e53935] transition-colors hover:bg-[#1e3347]"
              tabIndex={-1}
              aria-hidden="true"
            >
              Reject
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
