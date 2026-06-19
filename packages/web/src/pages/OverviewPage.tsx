import { KpiCard } from '@/components/overview/KpiCard'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { BookOpen, Activity, CheckCircle2, AlertTriangle } from 'lucide-react'
import type { Rule } from '@/types/rule'

interface OverviewPageProps {
  rules: Rule[]
}

export function OverviewPage({ rules }: OverviewPageProps) {
  const active = rules.filter(r => r.is_active)
  const avgEff = active.length ? active.reduce((s, r) => s + r.effectiveness_score, 0) / active.length : 0
  const pending = rules.filter(r => !r.is_active).length

  const effectivenessData = active
    .sort((a, b) => b.effectiveness_score - a.effectiveness_score)
    .slice(0, 8)
    .map(r => ({ name: r.name.slice(0, 20), score: Math.round(r.effectiveness_score * 100) }))

  const triggerData = active
    .sort((a, b) => b.times_triggered - a.times_triggered)
    .slice(0, 6)
    .map(r => ({ name: r.name.slice(0, 20), triggers: r.times_triggered }))

  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Active Rules"
          value={active.length}
          delta={`${pending} pending review`}
          status={active.length > 0 ? 'green' : 'neutral'}
          icon={<BookOpen className="w-6 h-6" />}
        />
        <KpiCard
          label="Avg Effectiveness"
          value={`${Math.round(avgEff * 100)}%`}
          status={avgEff >= 0.7 ? 'green' : avgEff >= 0.4 ? 'amber' : 'red'}
          icon={<Activity className="w-6 h-6" />}
        />
        <KpiCard
          label="Compliance Health"
          value="—"
          status="neutral"
          icon={<CheckCircle2 className="w-6 h-6" />}
        />
        <KpiCard
          label="Pending Review"
          value={pending}
          status={pending > 0 ? 'amber' : 'green'}
          icon={<AlertTriangle className="w-6 h-6" />}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader><CardTitle>Rule Effectiveness</CardTitle></CardHeader>
          <CardContent>
            {effectivenessData.length === 0 ? (
              <p className="text-sm text-muted-foreground py-8 text-center">No active rules yet</p>
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={effectivenessData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} />
                  <YAxis tick={{ fontSize: 11, fill: '#64748b' }} domain={[0, 100]} />
                  <Tooltip formatter={(v) => [`${v}%`, 'Effectiveness']} />
                  <Bar dataKey="score" fill="#4f46e5" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Most Triggered Rules</CardTitle></CardHeader>
          <CardContent>
            {triggerData.length === 0 ? (
              <p className="text-sm text-muted-foreground py-8 text-center">No trigger data yet</p>
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={triggerData} layout="vertical" margin={{ top: 4, right: 16, left: 4, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 11, fill: '#64748b' }} />
                  <YAxis dataKey="name" type="category" tick={{ fontSize: 11, fill: '#64748b' }} width={110} />
                  <Tooltip formatter={(v) => [v, 'Triggers']} />
                  <Bar dataKey="triggers" fill="#10b981" radius={[0, 3, 3, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
