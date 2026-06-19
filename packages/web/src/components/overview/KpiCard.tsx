import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'

interface KpiCardProps {
  label: string
  value: string | number
  delta?: string
  status?: 'green' | 'amber' | 'red' | 'neutral'
  icon?: React.ReactNode
}

export function KpiCard({ label, value, delta, status = 'neutral', icon }: KpiCardProps) {
  const statusColors = {
    green: 'text-emerald-600',
    amber: 'text-amber-600',
    red: 'text-red-600',
    neutral: 'text-muted-foreground',
  }
  const statusBg = {
    green: 'bg-emerald-50 border-emerald-200',
    amber: 'bg-amber-50 border-amber-200',
    red: 'bg-red-50 border-red-200',
    neutral: '',
  }

  return (
    <Card className={cn('transition-all', statusBg[status])}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide truncate">{label}</p>
            <p className={cn('text-2xl font-bold mt-1', statusColors[status])}>{value}</p>
            {delta && <p className="text-xs text-muted-foreground mt-1 truncate">{delta}</p>}
          </div>
          {icon && <div className={cn('text-2xl ml-3', statusColors[status])}>{icon}</div>}
        </div>
      </CardContent>
    </Card>
  )
}
