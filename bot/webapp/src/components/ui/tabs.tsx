import * as React from "react"

interface TabsProps {
  defaultValue?: string
  value?: string
  onValueChange?: (value: string) => void
  className?: string
  children: React.ReactNode
}

function Tabs({ defaultValue, value, onValueChange, className, children }: TabsProps) {
  const [selectedValue, setSelectedValue] = React.useState(value || defaultValue)
  
  React.useEffect(() => {
    if (value !== undefined) {
      setSelectedValue(value)
    }
  }, [value])

  const handleValueChange = (newValue: string) => {
    setSelectedValue(newValue)
    onValueChange?.(newValue)
  }

  return (
    <div className={className}>
      {React.Children.map(children, child => {
        if (!React.isValidElement(child)) return child
        
        if (child.type === TabsList || child.type === TabsContent) {
          return React.cloneElement(child, {
            selectedValue,
            onValueChange: handleValueChange
          })
        }
        
        return child
      })}
    </div>
  )
}

interface TabsListProps {
  className?: string
  children: React.ReactNode
  selectedValue?: string
  onValueChange?: (value: string) => void
}

function TabsList({ className, children, selectedValue, onValueChange }: TabsListProps) {
  return (
    <div className={`inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground ${className || ""}`}>
      {React.Children.map(children, child => {
        if (!React.isValidElement(child) || child.type !== TabsTrigger) return child
        
        return React.cloneElement(child, {
          selected: child.props.value === selectedValue,
          onClick: () => onValueChange?.(child.props.value)
        })
      })}
    </div>
  )
}

interface TabsTriggerProps {
  className?: string
  value: string
  selected?: boolean
  onClick?: () => void
  children: React.ReactNode
}

function TabsTrigger({ className, value, selected, onClick, children }: TabsTriggerProps) {
  return (
    <button
      className={`inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 ${
        selected 
          ? "bg-background text-foreground shadow-sm" 
          : "text-muted-foreground hover:text-foreground"
      } ${className || ""}`}
      onClick={onClick}
    >
      {children}
    </button>
  )
}

interface TabsContentProps {
  className?: string
  value: string
  selectedValue?: string
  children: React.ReactNode
}

function TabsContent({ className, value, selectedValue, children }: TabsContentProps) {
  if (value !== selectedValue) return null
  
  return (
    <div
      className={`mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${className || ""}`}
    >
      {children}
    </div>
  )
}

export { Tabs, TabsList, TabsTrigger, TabsContent } 