import * as React from "react"

interface AlertProps {
  variant?: "default" | "destructive"
  className?: string
  children: React.ReactNode
}

function Alert({ className, variant = "default", ...props }: AlertProps) {
  return (
    <div
      role="alert"
      className={`relative w-full rounded-lg border p-4 ${
        variant === "destructive"
          ? "border-destructive/50 text-destructive dark:border-destructive"
          : "border-border text-foreground"
      } ${className || ""}`}
      {...props}
    />
  )
}

interface AlertTitleProps {
  className?: string
  children: React.ReactNode
}

function AlertTitle({ className, ...props }: AlertTitleProps) {
  return (
    <h5
      className={`mb-1 font-medium leading-none tracking-tight ${className || ""}`}
      {...props}
    />
  )
}

interface AlertDescriptionProps {
  className?: string
  children: React.ReactNode
}

function AlertDescription({ className, ...props }: AlertDescriptionProps) {
  return (
    <div
      className={`text-sm ${className || ""}`}
      {...props}
    />
  )
}

export { Alert, AlertTitle, AlertDescription } 