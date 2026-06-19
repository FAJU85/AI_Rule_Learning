import { cn } from '@/lib/utils'

interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'success' | 'warning' | 'destructive' | 'outline'
}

export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <div className={cn(
      'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors',
      variant === 'default' && 'bg-primary text-primary-foreground',
      variant === 'success' && 'bg-emerald-100 text-emerald-700',
      variant === 'warning' && 'bg-amber-100 text-amber-700',
      variant === 'destructive' && 'bg-red-100 text-red-700',
      variant === 'outline' && 'border border-border text-foreground',
      className
    )} {...props} />
  )
}
