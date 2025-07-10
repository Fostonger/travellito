import * as React from "react"

interface SeparatorProps {
  className?: string
  orientation?: "horizontal" | "vertical"
}

function Separator({
  className,
  orientation = "horizontal",
  ...props
}: React.HTMLAttributes<HTMLDivElement> & SeparatorProps) {
  return (
    <div
      className={`shrink-0 bg-border ${
        orientation === "horizontal" ? "h-[1px] w-full" : "h-full w-[1px]"
      } ${className || ""}`}
      {...props}
    />
  )
}

export { Separator } 
 