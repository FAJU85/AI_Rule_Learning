import { cn } from '@/lib/utils'
import { LayoutDashboard, BookOpen, BarChart3, Shield, Settings, Brain, Upload, GitBranch } from 'lucide-react'

const nav = [
  { label: 'Overview', icon: LayoutDashboard, id: 'overview' },
  { label: 'Rules', icon: BookOpen, id: 'rules' },
  { label: 'Analytics', icon: BarChart3, id: 'analytics' },
  { label: 'Import Sessions', icon: Upload, id: 'import' },
  { label: 'Analysis', icon: Brain, id: 'analysis' },
  { label: 'Governance', icon: Shield, id: 'governance' },
  { label: 'Dependencies', icon: GitBranch, id: 'dependencies' },
  { label: 'Settings', icon: Settings, id: 'settings' },
]

interface SidebarProps {
  activeTab: string
  onTabChange: (tab: string) => void
}

export function Sidebar({ activeTab, onTabChange }: SidebarProps) {
  return (
    <aside className="w-60 shrink-0 border-r border-border bg-card h-screen sticky top-0 flex flex-col">
      <div className="p-6 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-primary flex items-center justify-center">
            <Brain className="w-4 h-4 text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">AI Rule Learning</p>
            <p className="text-xs text-muted-foreground">Smarter every session</p>
          </div>
        </div>
      </div>
      <nav className="flex-1 p-3 space-y-0.5">
        {nav.map(({ label, icon: Icon, id }) => (
          <button
            key={id}
            onClick={() => onTabChange(id)}
            className={cn(
              'w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors text-left',
              activeTab === id
                ? 'bg-primary/10 text-primary font-medium'
                : 'text-muted-foreground hover:bg-accent hover:text-foreground'
            )}
          >
            <Icon className="w-4 h-4 shrink-0" />
            {label}
          </button>
        ))}
      </nav>
      <div className="p-4 border-t border-border">
        <p className="text-xs text-muted-foreground">v0.1.0</p>
      </div>
    </aside>
  )
}
