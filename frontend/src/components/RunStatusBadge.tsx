import type { RunStatus } from '../types'
import clsx from 'clsx'

const statusStyles: Record<RunStatus, string> = {
  queued: 'bg-gray-100 text-gray-700',
  running: 'bg-blue-100 text-blue-700 animate-pulse',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  cancelled: 'bg-yellow-100 text-yellow-700',
}

const statusIcons: Record<RunStatus, string> = {
  queued: 'o',
  running: '*',
  completed: '+',
  failed: '-',
  cancelled: '/',
}

export default function RunStatusBadge({ status }: { status: RunStatus }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-medium',
        statusStyles[status]
      )}
    >
      <span>{statusIcons[status]}</span>
      <span className="capitalize">{status}</span>
    </span>
  )
}
