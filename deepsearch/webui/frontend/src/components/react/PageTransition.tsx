import React, { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { CSSTransition, TransitionGroup } from 'react-transition-group'
import './PageTransition.scss'

const PageTransition = ({ children }) => {
  const location = useLocation()
  const nodeRef = useRef(null)

  useEffect(() => {
    // 页面切换时滚动到顶部
    window.scrollTo(0, 0)
  }, [location])

  return (
    <TransitionGroup className="page-transition-container">
      <CSSTransition
        key={location.pathname}
        classNames="page"
        timeout={300}
        nodeRef={nodeRef}
        unmountOnExit
      >
        <div ref={nodeRef} className="page-transition-wrapper">
          {children}
        </div>
      </CSSTransition>
    </TransitionGroup>
  )
}

export default PageTransition